import warnings
from logging import getLogger
from typing import List, Optional, Dict, Union, Literal
import numpy as np

from geniml.region2vec import Region2VecExModel
from geniml.io import RegionSet

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

import os

from bbconf.const import (
    PKG_NAME,
)
from bbconf.models.bed_models import (
    BedMetadata,
    BedFiles,
    FileModel,
    BedPlots,
    BedClassification,
    BedStats,
    BedPEPHub,
)
from bbconf.exceptions import (
    BedBaseConfError,
)
from bbconf.db_utils import BaseEngine, Bed, Files
from bbconf.config_parser.bedbaseconfig import BedBaseConfig

_LOGGER = getLogger(PKG_NAME)


BIGBED_PATH_FOLDER = "bigbed_files"
BED_PATH_FOLDER = "bed_files"
PLOTS_PATH_FOLDER = "stats"


class BedAgentBedFile:
    """
    Class that represents Bedfile in Database.

    This class has method to add, delete, get files and metadata from the database.
    """

    def __init__(self, config: BedBaseConfig):
        """
        :param config: config object with database and qdrant engine and credentials
        """
        self._sa_engine = config.db_engine.engine
        self._db_engine = config.db_engine
        self._qdrant_engine = config.qdrant_engine
        self._boto3_client = config.boto3_client
        self._config = config

    def get(self, identifier: str) -> BedMetadata:
        """
        Get file metadata by identifier.

        :param identifier: bed file identifier
        :return: project metadata
        """
        statement = select(Bed).where(Bed.id == identifier)

        bed_plots = BedPlots()
        bed_files = BedFiles()

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)

            for result in bed_object.files:
                # PLOTS
                if result.name in BedPlots.model_fields:
                    setattr(bed_plots, result.name, FileModel(
                        name=result.name,
                        path=result.path,
                        size=result.size,
                        path_thumbnail=result.path_thumbnail,
                        description=result.description
                    ))
                # FILES
                elif result.name in BedFiles.model_fields:
                    setattr(bed_files, result.name, FileModel(
                        name=result.name,
                        path=result.path,
                        size=result.size,
                        description=result.description
                    ))
                else:
                    _LOGGER.error(f"Unknown file type: {result.name}. And is not in the model fields. Skipping..")

            bed_stats = BedStats(**bed_object.__dict__)
            bed_classification = BedClassification(**bed_object.__dict__)

        try:
            bed_metadata = self._config.phc.sample.get(
                namespace=self._config.config.phc.namespace,
                name=self._config.config.phc.name,
                tag=self._config.config.phc.tag,
                sample_name=identifier,
            )
        except Exception as e:
            _LOGGER.warning(f"Could not retrieve metadata from pephub. Error: {e}")
            bed_metadata = {}

        return BedMetadata(
            id=bed_object.id,
            name=bed_object.name,
            stats=bed_stats,
            classification=bed_classification,
            plots=bed_plots,
            files=bed_files,
            description=bed_object.description,
            submission_date=bed_object.submission_date,
            last_update_date=bed_object.last_update_date,
            raw_metadata=BedPEPHub(**bed_metadata),
        )

    def get_stats(self, identifier: str) -> BedStats:
        """
        Get file statistics by identifier.

        :param identifier: bed file identifier

        :return: project statistics as BedStats object
        """
        statement = select(Bed).where(Bed.id == identifier)

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)
            bed_stats = BedStats(**bed_object.__dict__)

        return bed_stats

    def get_plots(self, identifier: str) -> BedPlots:
        """
        Get file plots by identifier.

        :param identifier: bed file identifier
        :return: project plots
        """
        statement = select(Bed).where(Bed.id == identifier)

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)
            bed_plots = BedPlots()
            for result in bed_object.files:
                if result.name in BedPlots.model_fields:
                    setattr(bed_plots, result.name, FileModel(
                        name=result.name,
                        path=result.path,
                        path_thumbnail=result.path_thumbnail,
                        description=result.description
                    ))
        return bed_plots

    def get_files(self, identifier: str) -> BedFiles:
        """
        Get file files by identifier.

        :param identifier: bed file identifier
        :return: project files
        """
        statement = select(Bed).where(Bed.id == identifier)

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)
            bed_files = BedFiles()
            for result in bed_object.files:
                if result.name in BedFiles.model_fields:
                    setattr(bed_files, result.name, FileModel(
                        name=result.name,
                        path=result.path,
                        description=result.description
                    ))
        return bed_files

    def get_raw_metadata(self, identifier: str) -> BedPEPHub:
        """
        Get file metadata by identifier.

        :param identifier: bed file identifier
        :return: project metadata
        """
        try:
            bed_metadata = self._config.phc.sample.get(
                namespace=self._config.config.phc.namespace,
                name=self._config.config.phc.name,
                tag=self._config.config.phc.tag,
                sample_name=identifier,
            )
        except Exception as e:
            _LOGGER.warning(f"Could not retrieve metadata from pephub. Error: {e}")
            bed_metadata = {}
        return BedPEPHub(**bed_metadata)

    def get_classification(self, identifier: str) -> BedClassification:
        """
        Get file classification by identifier.

        :param identifier: bed file identifier
        :return: project classification
        """
        statement = select(Bed).where(Bed.id == identifier)

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)
            bed_classification = BedClassification(**bed_object.__dict__)

        return bed_classification

    def get_objects(self, identifier: str) -> Dict[str, FileModel]:
        """
        Get all object related to bedfile

        :param identifier:  bed file identifier
        :return: project objects dict
        """
        statement = select(Bed).where(Bed.id == identifier)
        return_dict = {}

        with Session(self._sa_engine) as session:
            bed_object = session.scalar(statement)
            for result in bed_object.files:
                return_dict[result.name] = FileModel(**result.__dict__)

        return return_dict


    def add(
        self,
        identifier: str,
        stats: dict,
        metadata: dict = None,
        plots: dict = None,
        files: dict = None,
        classification: dict = None,
        add_to_qdrant: bool = False,
        upload_pephub: bool = False,
        upload_s3: bool = False,
        local_path: str = None,
        overwrite: bool = False,
    ) -> None:
        """
        Add bed file to the database.

        :param identifier: bed file identifier
        :param stats: bed file results {statistics, plots, files, metadata}
        :param metadata: bed file metadata (will be saved in pephub)
        :param plots: bed file plots
        :param files: bed file files
        :param classification: bed file classification
        :param add_to_qdrant: add bed file to qdrant indexs
        :param upload_pephub: add bed file to pephub
        :param upload_s3: upload files to s3
        :param local_path: local path to the output files
        :param overwrite: overwrite bed file if it already exists
        :return: None
        """
        _LOGGER.info(f"Adding bed file to database. bed_id: {identifier}")


        stats = BedStats(**stats)
        # TODO: we should not check for specific keys, of the plots!
        plots = BedPlots(**plots)
        files = BedFiles(**files)
        metadata = BedPEPHub(**metadata)
        classification = BedClassification(**classification)

        if upload_pephub:
            self.upload_pephub(identifier, metadata.model_dump(), overwrite)
        else:
            _LOGGER.info("upload_pephub set to false. Skipping pephub..")

        if add_to_qdrant:
            self.upload_qdrant(identifier, files.bed_file.path, metadata.model_dump())
        else:
            _LOGGER.info("add_to_qdrant set to false. Skipping qdrant..")

        # Upload files to s3
        if upload_s3:
            if files:
                files = self.upload_files_s3(files)

            if plots:
                plots = self.upload_plots_s3(
                    identifier, output_path=local_path, plots=plots
                )

        with Session(self._sa_engine) as session:
            new_bed = Bed(
                id=identifier,
                **stats.model_dump(),
                **classification.model_dump(),
            )
            session.add(new_bed)
            if upload_s3:
                for k, v in files:
                    if v:
                        new_file = Files(
                            name=k,
                            path=v.path,
                            description=v.description,
                            bedfile_id=identifier,
                            type="file",
                            size=v.size,
                        )
                        session.add(new_file)
                for k, v in plots:
                    if v:
                        new_plot = Files(
                            name=k,
                            path=v.path,
                            path_thumbnail=v.path_thumbnail,
                            description=v.description,
                            bedfile_id=identifier,
                            type="plot"
                        )
                        session.add(new_plot)

            session.commit()

        return None

    def delete(self, identifier: str) -> None:
        """
        Delete bed file from the database.

        :param identifier: bed file identifier
        :return: None
        """
        ...

    def upload_files_s3(self, files: BedFiles) -> BedFiles:
        """
        Upload files to s3.

        :param files: dictionary with files to upload
        :return: None
        """

        if files.bed_file:
            file_base_name = os.path.basename(files.bed_file.path)

            bed_file_path = files.bed_file.path
            bed_s3_path = os.path.join(
                BED_PATH_FOLDER,
                file_base_name[0],
                file_base_name[1],
                os.path.basename(bed_file_path),
            )
            self._upload_s3(bed_file_path, bed_s3_path)

            files.bed_file.path = bed_s3_path

        if files.bigbed_file:
            file_base_name = os.path.basename(files.bigbed_file.path)

            bed_file = files.bigbed_file.path
            bigbed_s3_path = os.path.join(
                BIGBED_PATH_FOLDER,
                file_base_name[0],
                file_base_name[1],
                os.path.basename(bed_file),
            )
            self._upload_s3(bed_file, bigbed_s3_path)

            files.bigbed_file.path = bigbed_s3_path

        return files

    def upload_plots_s3(
        self, identifier: str, output_path: str, plots: BedPlots
    ) -> BedPlots:
        """
        Upload plots to s3.

        :param identifier: bed file identifier
        :param plots: dictionary with plots to upload
        :param output_path: local path to the output files
        :return: None
        """
        _LOGGER.info(f"Uploading plots to S3...")

        plots_output = BedPlots()
        output_folder = os.path.join(PLOTS_PATH_FOLDER, identifier)

        for key, value in plots:
            if value:
                if value.path:
                    file_s3_path = os.path.join(
                        output_folder, os.path.basename(value.path)
                    )
                    local_path = os.path.join(output_path, value.path)
                    self._upload_s3(local_path, file_s3_path)
                else:
                    file_s3_path = None
                if value.path_thumbnail:
                    file_s3_path_thumbnail = os.path.join(
                        output_folder, os.path.basename(value.path_thumbnail)
                    )
                    local_path_thumbnail = os.path.join(
                        output_path, value.path_thumbnail
                    )
                    self._upload_s3(local_path_thumbnail, file_s3_path_thumbnail)
                else:
                    file_s3_path_thumbnail = None

                setattr(
                    plots_output,
                    key,
                    FileModel(
                        name=value.name,
                        path=file_s3_path,
                        path_thumbnail=file_s3_path_thumbnail,
                        description=value.description,
                    ),
                )

        return plots_output

    def _upload_s3(self, file_path: str, s3_path: str) -> None:
        """
        Upload file to s3.

        :param file_path: local path to the file
        :param s3_path: path to the file in s3 with file name
        :return: None
        """
        self._config.boto3_client.upload_file(
            file_path, self._config.config.s3.bucket, s3_path
        )

    def upload_pephub(self, identifier: str, metadata: dict, overwrite: bool = False):
        if not metadata:
            _LOGGER.warning("No metadata provided. Skipping pephub upload..")
            return False
        self._config.phc.sample.create(
            namespace=self._config.config.phc.namespace,
            name=self._config.config.phc.name,
            tag=self._config.config.phc.tag,
            sample_name=identifier,
            sample_dict=metadata,
            overwrite=overwrite,
        )

    def upload_qdrant(
        self,
        bed_id: str,
        bed_file: Union[str, RegionSet],
        payload: dict = None,
        region_to_vec: Region2VecExModel = None,
    ) -> None:
        """
        Convert bed file to vector and add it to qdrant database

        :param bed_id: bed file id
        :param bed_file: path to the bed file, or RegionSet object
        :param payload: additional metadata to store alongside vectors
        :param region_to_vec: initiated region to vector model. If None, new object will be created.
        :return: None
        """

        _LOGGER.info(f"Adding bed file to qdrant. bed_id: {bed_id}")
        if isinstance(bed_file, str):
            bed_region_set = RegionSet(bed_file)
        elif isinstance(bed_file, RegionSet):
            bed_region_set = bed_file
        else:
            raise BedBaseConfError(
                "Could not add add region to qdrant. Invalid type, or path. "
            )
        if not region_to_vec and isinstance(self._config.config.path.region2vec, str):
            reg_2_vec_obj = Region2VecExModel(self._config.config.path.region2vec)
        else:
            reg_2_vec_obj = region_to_vec
        bed_embedding = np.mean(reg_2_vec_obj.encode(bed_region_set), axis=0)

        # Upload bed file vector to the database
        vec_dim = bed_embedding.shape[0]
        self._qdrant_engine.load(
            ids=[bed_id],
            vectors=bed_embedding.reshape(1, vec_dim),
            payloads=[{**payload}],
        )
        return None

    def text_to_bed_search(self, query: str, limit: int = 10, offset: int = 0):
        """
        Search for bed files by text query in qdrant database

        :param query: text query
        :param limit: number of results to return
        :param offset: offset to start from

        :return: list of bed file metadata
        """
        _LOGGER.info(f"Looking for: {query}")
        _LOGGER.info(f"Using backend: {self._config.t2bsi}")

        # TODO: FIX it!
        results = self._config.t2bsi.nl_vec_search(query, limit=limit, offset=offset)
        for result in results:
            try:
                # qdrant automatically adds hypens to the ids. remove them.
                result["metadata"] = bbc.bed.retrieve_one(result["id"].replace("-", ""))
            except RecordNotFoundError:
                _LOGGER.info(
                    f"Couldn't find qdrant result in bedbase for id: {result['id']}"
                )
        return results
