import sys
from typing import List, Dict, Any, Tuple, Set
import logging
import numpy as np
import pandas as pd

from d3m import container, utils
from d3m.metadata.pipeline import Pipeline, PrimitiveStep
from d3m.metadata.base import ArgumentType
from d3m.metadata import hyperparams

from distil.primitives.categorical_imputer import CategoricalImputerPrimitive
from distil.primitives.ensemble_forest import EnsembleForestPrimitive
from distil.primitives.replace_singletons import ReplaceSingletonsPrimitive
from distil.primitives.one_hot_encoder import OneHotEncoderPrimitive
from distil.primitives.binary_encoder import BinaryEncoderPrimitive
from distil.primitives.text_encoder import TextEncoderPrimitive
from distil.primitives.enrich_dates import EnrichDatesPrimitive

from common_primitives.dataset_to_dataframe import DatasetToDataFramePrimitive
from common_primitives.remove_columns import RemoveColumnsPrimitive
from common_primitives.column_parser import ColumnParserPrimitive
from common_primitives.construct_predictions import ConstructPredictionsPrimitive
from common_primitives.extract_columns_semantic_types import ExtractColumnsBySemanticTypesPrimitive

from sklearn_wrap import SKMissingIndicator
from sklearn_wrap import SKImputer
from sklearn_wrap import SKStandardScaler

PipelineContext = utils.Enum(value='PipelineContext', names=['TESTING'], start=1)

# CDB: Totally unoptimized.  Pipeline creation code could be simplified but has been left
# in a naively implemented state for readability for now.
def create_pipeline(metric: str,
                    cat_mode: str = 'one_hot',
                    max_one_hot: int = 16,
                    scale: bool = False) -> Pipeline:
    input_val = 'steps.{}.produce'


    # create the basic pipeline
    tabular_pipeline = Pipeline(context=PipelineContext.TESTING)
    tabular_pipeline.add_input(name='inputs')

    # extract dataframe from dataset
    step = PrimitiveStep(primitive_description=DatasetToDataFramePrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='inputs.0')
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step = 0

    # Parse columns.
    step = PrimitiveStep(primitive_description=ColumnParserPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    semantic_types = ('http://schema.org/Boolean', 'http://schema.org/Integer', 'http://schema.org/Float',
                      'https://metadata.datadrivendiscovery.org/types/FloatVector')
    step.add_hyperparameter('parse_semantic_types', ArgumentType.VALUE, semantic_types)
    tabular_pipeline.add_step(step)
    previous_step += 1
    parse_step = previous_step

    # Extract attributes
    step = PrimitiveStep(primitive_description=ExtractColumnsBySemanticTypesPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(parse_step))
    step.add_output('produce')
    step.add_hyperparameter('semantic_types', ArgumentType.VALUE, ('https://metadata.datadrivendiscovery.org/types/Attribute',))
    tabular_pipeline.add_step(step)
    previous_step += 1
    attributes_step = previous_step

    # Extract targets
    step = PrimitiveStep(primitive_description=ExtractColumnsBySemanticTypesPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(parse_step))
    step.add_output('produce')
    target_types = ('https://metadata.datadrivendiscovery.org/types/Target', 'https://metadata.datadrivendiscovery.org/types/TrueTarget')
    step.add_hyperparameter('semantic_types', ArgumentType.VALUE, target_types)
    tabular_pipeline.add_step(step)
    previous_step += 1
    target_step = previous_step

    # Append date enricher.  Looks for date columns and normalizes them.
    step = PrimitiveStep(primitive_description=EnrichDatesPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(attributes_step))
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Append singleton replacer.  Looks for categorical values that only occur once in a column and replace them with a flag.
    step = PrimitiveStep(primitive_description=ReplaceSingletonsPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Append categorical imputer.  Finds missing categorical values and replaces them with an imputed value.
    step = PrimitiveStep(primitive_description=CategoricalImputerPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Adds an svm text encoder for text fields.
    step = PrimitiveStep(primitive_description=TextEncoderPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_argument(name='outputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(target_step))
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step += 1

    """
    # Adds a one hot encoder for categoricals of low cardinality.
    if cat_mode == 'one_hot':
        step = PrimitiveStep(primitive_description=OneHotEncoderPrimitive.metadata.query())
        step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
        step.add_output('produce')
        step.add_hyperparameter('max_one_hot', ArgumentType.VALUE, max_one_hot)
        tabular_pipeline.add_step(step)
        previous_step += 1
    """
    # Adds a binary encoder for categoricals of high cardinality.
    step = PrimitiveStep(primitive_description=BinaryEncoderPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    if cat_mode == 'one_hot':
        step.add_hyperparameter('min_binary', ArgumentType.VALUE, max_one_hot + 1)
    else:
        step.add_hyperparameter('min_binary', ArgumentType.VALUE, 0)
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Adds SK learn missing value indicator
    step = PrimitiveStep(primitive_description=SKMissingIndicator.SKMissingIndicator.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    step.add_hyperparameter('use_semantic_types', ArgumentType.VALUE, True)
    step.add_hyperparameter('return_result', ArgumentType.VALUE, 'append')
    step.add_hyperparameter('error_on_new', ArgumentType.VALUE, False)
    step.add_hyperparameter('error_on_no_input', ArgumentType.VALUE, False)
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Adds SK learn simple imputer
    step = PrimitiveStep(primitive_description=SKImputer.SKImputer.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_output('produce')
    step.add_hyperparameter('use_semantic_types', ArgumentType.VALUE, True)
    step.add_hyperparameter('error_on_no_input', ArgumentType.VALUE, False)
    step.add_hyperparameter('return_result', ArgumentType.VALUE, 'replace')
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Append scaler for numerical values.
    if scale:
        step = PrimitiveStep(primitive_description=SKStandardScaler.SKStandardScaler.metadata.query())
        step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
        step.add_output('produce')
        step.add_hyperparameter('use_semantic_types', ArgumentType.VALUE, True)
        step.add_hyperparameter('return_result', ArgumentType.VALUE, 'replace')
        tabular_pipeline.add_step(step)
        previous_step += 1

    # Generates a random forest ensemble model.
    step = PrimitiveStep(primitive_description=EnsembleForestPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_argument(name='outputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(target_step))
    step.add_output('produce')
    step.add_hyperparameter('metric', ArgumentType.VALUE, metric)
    tabular_pipeline.add_step(step)
    previous_step += 1

    # # convert predictions to expected format
    step = PrimitiveStep(primitive_description=ConstructPredictionsPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(previous_step))
    step.add_argument(name='reference', argument_type=ArgumentType.CONTAINER, data_reference=input_val.format(parse_step))
    step.add_output('produce')
    tabular_pipeline.add_step(step)
    previous_step += 1

    # Adding output step to the pipeline
    tabular_pipeline.add_output(name='output', data_reference=input_val.format(previous_step))

    return tabular_pipeline
