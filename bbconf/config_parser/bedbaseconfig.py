from pathlib import Path
from typing import Union, List
import yacman
import logging
from geniml.search import QdrantBackend
import qdrant_client
from geniml.text2bednn import text2bednn
from fastembed.embedding import FlagEmbedding
from geniml.region2vec import Region2VecExModel
import warnings
import os

from pephubclient import PEPHubClient
import boto3


from bbconf.db_utils import BaseEngine
from bbconf.const import (
    PKG_NAME,
)
from bbconf.models.bed_models import BedFiles, BedPlots
from bbconf.models.bedset_models import BedSetPlots
from bbconf.models.base_models import FileModel
from bbconf.helpers import get_bedbase_cfg, get_absolute_path
from bbconf.config_parser.models import ConfigFile
from bbconf.config_parser.const import (
    S3_FILE_PATH_FOLDER,
    S3_PLOTS_PATH_FOLDER,
    S3_BEDSET_PATH_FOLDER,
)
from bbconf.exceptions import BedbaseS3ConnectionError, BedBaseConfError


_LOGGER = logging.getLogger(PKG_NAME)


class BedBaseConfig:
    def __init__(self, config: Union[Path, str]):

        self.cfg_path = get_bedbase_cfg(config)
        self._config = self._read_config_file(self.cfg_path)

        self._db_engine = self._init_db_engine()
        self._qdrant_engine = self._init_qdrant_backend()
        self._t2bsi = self._init_t2bsi_object()
        self._r2v = self._init_r2v_object()

        self._phc = self._init_pephubclient()
        self._boto3_client = self._init_boto3_client()

    @staticmethod
    def _read_config_file(config_path: str) -> ConfigFile:
        """
        Read configuration file and insert default values if not set

        :param config_path: configuration file path
        :return: None
        :raises: raise_missing_key (if config key is missing)
        """
        _config = yacman.YAMLConfigManager(filepath=config_path).exp

        config_dict = {}
        for field_name, annotation in ConfigFile.model_fields.items():
            try:
                config_dict[field_name] = annotation.annotation(
                    **_config.get(field_name)
                )
            except TypeError:
                # TODO: this should be more specific
                config_dict[field_name] = annotation.annotation()

        return ConfigFile(**config_dict)

    @property
    def config(self) -> ConfigFile:
        """
        Get configuration

        :return: configuration object
        """
        return self._config

    @property
    def db_engine(self) -> BaseEngine:
        """
        Get database engine

        :return: database engine
        """
        return self._db_engine

    @property
    def t2bsi(self) -> Union[text2bednn.Text2BEDSearchInterface, None]:
        """
        Get text2bednn object

        :return: text2bednn object
        """
        return self._t2bsi

    @property
    def r2v(self) -> Region2VecExModel:
        """
        Get region2vec object

        :return: region2vec object
        """
        return self._r2v

    @property
    def qdrant_engine(self) -> QdrantBackend:
        """
        Get qdrant engine

        :return: qdrant engine
        """
        return self._qdrant_engine

    @property
    def phc(self) -> PEPHubClient:
        """
        Get PEPHub client

        :return: PEPHub client
        """
        return self._phc

    @property
    def boto3_client(self) -> boto3.client:
        """
        Get boto3 client

        :return: boto3 client
        """
        return self._boto3_client

    def _init_db_engine(self) -> BaseEngine:
        return BaseEngine(
            host=self._config.database.host,
            port=self._config.database.port,
            database=self._config.database.database,
            user=self._config.database.user,
            password=self._config.database.password,
            drivername="postgresql+psycopg",
        )

    def _init_qdrant_backend(self) -> QdrantBackend:
        """
        Create qdrant client object using credentials provided in config file

        :return: QdrantClient
        """
        try:
            return QdrantBackend(
                collection=self._config.qdrant.collection,
                qdrant_host=self._config.qdrant.host,
                qdrant_port=self._config.qdrant.port,
                qdrant_api_key=self._config.qdrant.api_key,
            )
        except qdrant_client.http.exceptions.ResponseHandlingException as err:
            _LOGGER.error(f"error in Connection to qdrant! skipping... Error: {err}")
            warnings.warn(
                f"error in Connection to qdrant! skipping... Error: {err}", UserWarning
            )

    def _init_t2bsi_object(self) -> Union[text2bednn.Text2BEDSearchInterface, None]:
        """
        Create Text 2 BED search interface and return this object

        :return: Text2BEDSearchInterface object
        """

        try:
            return text2bednn.Text2BEDSearchInterface(
                nl2vec_model=FlagEmbedding(model_name=self._config.path.text2vec),
                vec2vec_model=self._config.path.vec2vec,
                search_backend=self.qdrant_engine,
            )
        except Exception as e:
            _LOGGER.error("Error in creating Text2BEDSearchInterface object: " + str(e))
            warnings.warn(
                "Error in creating Text2BEDSearchInterface object: " + str(e),
                UserWarning,
            )
            return None

    @staticmethod
    def _init_pephubclient() -> Union[PEPHubClient, None]:
        """
        Create Pephub client object using credentials provided in config file

        :return: PephubClient
        """
        try:
            return PEPHubClient()
        except Exception as e:
            _LOGGER.error(f"Error in creating PephubClient object: {e}")
            warnings.warn(f"Error in creating PephubClient object: {e}", UserWarning)
            return None

    def _init_boto3_client(
        self,
    ) -> boto3.client:
        """
        Create Pephub client object using credentials provided in config file

        :return: PephubClient
        """
        try:
            return boto3.client(
                "s3",
                endpoint_url=self._config.s3.endpoint_url,
                aws_access_key_id=self._config.s3.aws_access_key_id,
                aws_secret_access_key=self._config.s3.aws_secret_access_key,
            )
        except Exception as e:
            _LOGGER.error(f"Error in creating boto3 client object: {e}")
            warnings.warn(f"Error in creating boto3 client object: {e}", UserWarning)
            return None

    def _init_r2v_object(self) -> Region2VecExModel:
        """
        Create Region2VecExModel object using credentials provided in config file
        """
        return Region2VecExModel(self.config.path.region2vec)

    def upload_s3(self, file_path: str, s3_path: Union[Path, str]) -> None:
        """
        Upload file to s3.

        :param file_path: local path to the file
        :param s3_path: path to the file in s3 with file name
        :return: None
        """
        if not self._boto3_client:
            _LOGGER.warning(
                "Could not upload file to s3. Connection to s3 not established. Skipping.."
            )
            raise BedbaseS3ConnectionError(
                "Could not upload file to s3. Connection error."
            )
        if not os.path.exists(file_path):
            raise BedBaseConfError(f"File {file_path} does not exist.")
        return self._boto3_client.upload_file(file_path, self.config.s3.bucket, s3_path)

    def upload_files_s3(
        self,
        identifier: str,
        files: Union[BedFiles, BedPlots, BedSetPlots],
        base_path: str,
        type: str = "files",
    ) -> Union[BedFiles, BedPlots, BedSetPlots]:
        """
        Upload files to s3.

        :param identifier: bed file identifier
        :param files: dictionary with files to upload
        :param base_path: local path to the output files
        :param type: type of files to upload [files, plots, bedsets]
        :return: None
        """

        if type == "files":
            s3_output_base_folder = S3_FILE_PATH_FOLDER
        elif type == "plots":
            s3_output_base_folder = S3_PLOTS_PATH_FOLDER
        elif type == "bedsets":
            s3_output_base_folder = S3_BEDSET_PATH_FOLDER
        else:
            raise BedBaseConfError(
                f"Invalid type: {type}. Should be 'files' or 'plots'"
            )

        for key, value in files:
            if not value:
                continue
            file_base_name = os.path.basename(value.path)
            file_path = get_absolute_path(value.path, base_path)
            s3_path = os.path.join(
                s3_output_base_folder,
                identifier[0],
                identifier[1],
                file_base_name,
            )
            self.upload_s3(file_path, s3_path=s3_path)

            setattr(value, "size", os.path.getsize(file_path))
            setattr(value, "path", s3_path)

            if value.path_thumbnail:
                file_base_name_thumbnail = os.path.basename(value.path_thumbnail)
                file_path_thumbnail = get_absolute_path(value.path_thumbnail, base_path)
                s3_path_thumbnail = os.path.join(
                    s3_output_base_folder,
                    identifier[0],
                    identifier[1],
                    file_base_name_thumbnail,
                )
                self.upload_s3(file_path_thumbnail, s3_path=s3_path_thumbnail)
                setattr(value, "path_thumbnail", s3_path_thumbnail)

        return files

    def delete_s3(self, s3_path: str) -> None:
        """
        Delete file from s3.

        :param s3_path: path to the file in s3
        :return: None
        """
        if not self._boto3_client:
            _LOGGER.warning(
                "Could not delete file from s3. Connection to s3 not established. Skipping.."
            )
            raise BedbaseS3ConnectionError(
                "Could not delete file from s3. Connection error."
            )
        return self._boto3_client.delete_object(
            Bucket=self.config.s3.bucket, Key=s3_path
        )

    def delete_files_s3(self, files: List[FileModel]) -> None:
        """
        Delete files from s3.

        :param files: list of file objects
        :return: None
        """
        for file in files:
            self.delete_s3(file.path)
            if file.path_thumbnail:
                self.delete_s3(file.path_thumbnail)
        return None
