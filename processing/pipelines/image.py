import sys
from typing import List, Dict, Any, Tuple, Set
import logging
import numpy as np
import pandas as pd

from d3m import container, utils
from d3m.metadata.pipeline import Pipeline, PrimitiveStep
from d3m.metadata.base import ArgumentType
from d3m.metadata import hyperparams

from common_primitives.dataset_to_dataframe import DatasetToDataFramePrimitive
from common_primitives.construct_predictions import ConstructPredictionsPrimitive
from common_primitives.denormalize import DenormalizePrimitive
from common_primitives.dataframe_image_reader import DataFrameImageReaderPrimitive
from common_primitives.extract_columns_semantic_types import ExtractColumnsBySemanticTypesPrimitive
from common_primitives.column_parser import ColumnParserPrimitive


from distil.primitives.ensemble_forest import EnsembleForestPrimitive
from distil.primitives.image_transfer import ImageTransferPrimitive

PipelineContext = utils.Enum(value='PipelineContext', names=['TESTING'], start=1)

# CDB: Totally unoptimized.  Pipeline creation code could be simplified but has been left
# in a naively implemented state for readability for now.
#
# Overall implementation relies on passing the entire dataset through the pipeline, with the primitives
# identifying columns to operate on based on type.  Alternative implementation (that better lines up with
# D3M approach, but generates more complex pipelines) would be to extract sub-sets by semantic type using
# a common primitive, apply the type-specific primitive to the sub-set, and then merge the changes
# (replace or join) back into the original data.
def create_pipeline(metric: str,
                    cat_mode: str = 'one_hot',
                    max_one_hot: int = 16,
                    scale: bool = False) -> Pipeline:

    # create the basic pipeline
    image_pipeline = Pipeline(context=PipelineContext.TESTING)
    image_pipeline.add_input(name='inputs')


    # step 0 - denormalize dataframe (N.B.: injects semantic type information)
    step = PrimitiveStep(primitive_description=DenormalizePrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='inputs.0')
    step.add_output('produce')
    image_pipeline.add_step(step)


    # step 1 - extract dataframe from dataset
    step = PrimitiveStep(primitive_description=DatasetToDataFramePrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.0.produce')
    step.add_output('produce')
    image_pipeline.add_step(step)


    # step 2 - read images
    step = PrimitiveStep(primitive_description=DataFrameImageReaderPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.1.produce')
    step.add_output('produce')
    step.add_hyperparameter('use_columns', ArgumentType.VALUE,[0,1])
    step.add_hyperparameter('return_result', ArgumentType.VALUE, 'replace')
    image_pipeline.add_step(step)


    # step 3 - parse columns
    step = PrimitiveStep(primitive_description=ColumnParserPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.2.produce')
    step.add_output('produce')
    semantic_types = ('http://schema.org/Boolean', 'http://schema.org/Integer', 'http://schema.org/Float',
                      'https://metadata.datadrivendiscovery.org/types/FloatVector')
    step.add_hyperparameter('parse_semantic_types', ArgumentType.VALUE, semantic_types)
    image_pipeline.add_step(step)


    # step 4 - featurize images
    step = PrimitiveStep(primitive_description=ImageTransferPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.3.produce')
    step.add_output('produce')
    image_pipeline.add_step(step)
    

    # step 5 - extract targets
    step = PrimitiveStep(primitive_description=ExtractColumnsBySemanticTypesPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.3.produce')
    step.add_output('produce')
    target_types = ('https://metadata.datadrivendiscovery.org/types/Target', 'https://metadata.datadrivendiscovery.org/types/TrueTarget')
    step.add_hyperparameter('semantic_types', ArgumentType.VALUE, target_types)
    image_pipeline.add_step(step)


    # step 6 - Generates a random forest ensemble model.
    step = PrimitiveStep(primitive_description=EnsembleForestPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.4.produce')
    step.add_argument(name='outputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.5.produce')
    step.add_output('produce')
    step.add_hyperparameter('metric', ArgumentType.VALUE, metric)
    image_pipeline.add_step(step)


    # step 7 - convert predictions to expected format
    step = PrimitiveStep(primitive_description=ConstructPredictionsPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.6.produce')
    step.add_argument(name='reference', argument_type=ArgumentType.CONTAINER, data_reference='steps.1.produce')
    step.add_output('produce')
    step.add_hyperparameter('use_columns', ArgumentType.VALUE, [0, 1])
    image_pipeline.add_step(step)


    # Adding output step to the pipeline
    image_pipeline.add_output(name='output', data_reference='steps.7.produce')

    return image_pipeline
