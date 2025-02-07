import sys
from typing import List, Dict, Any, Tuple, Set
import logging
import numpy as np
import pandas as pd

from d3m import container, utils
from d3m.metadata.pipeline import Pipeline, PrimitiveStep
from d3m.metadata.base import ArgumentType
from d3m.metadata import hyperparams

from distil.primitives.load_single_graph import DistilSingleGraphLoaderPrimitive
from distil.primitives.community_detection import DistilCommunityDetectionPrimitive

from common_primitives.dataset_to_dataframe import DatasetToDataFramePrimitive
from common_primitives.construct_predictions import ConstructPredictionsPrimitive

PipelineContext = utils.Enum(value='PipelineContext', names=['TESTING'], start=1)



def create_pipeline(metric: str) -> Pipeline:

    # create the basic pipeline
    vertex_nomination_pipeline = Pipeline(context=PipelineContext.TESTING)
    vertex_nomination_pipeline.add_input(name='inputs')

    # step 0 - extract the graphs
    step = PrimitiveStep(primitive_description=DistilSingleGraphLoaderPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='inputs.0')
    step.add_output('produce')
    step.add_output('produce_target')
    vertex_nomination_pipeline.add_step(step)

    # step 1 - nominate
    step = PrimitiveStep(primitive_description=DistilCommunityDetectionPrimitive.metadata.query())
    step.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.0.produce')
    step.add_argument(name='outputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.0.produce_target')
    step.add_hyperparameter('metric', ArgumentType.VALUE, metric)
    step.add_output('produce')
    vertex_nomination_pipeline.add_step(step)

    # Adding output step to the pipeline
    vertex_nomination_pipeline.add_output(name='output', data_reference='steps.1.produce')

    return vertex_nomination_pipeline