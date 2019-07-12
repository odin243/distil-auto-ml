from d3m import index
from d3m.metadata.base import ArgumentType, Context
from d3m.metadata.pipeline import Pipeline, PrimitiveStep
import sys

def create_pipeline(metric: str) -> Pipeline:
    # Creating pipeline
    pipeline_description = Pipeline()
    pipeline_description.add_input(name='inputs')

    # Step 0: Denormalize primitive
    step_0 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_transformation.denormalize.Common'))
    step_0.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='inputs.0')
    step_0.add_output('produce')
    pipeline_description.add_step(step_0)

    # Step 1: DISTIL/NK Storc primitive
    step_1 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.clustering.hdbscan.Hdbscan'))
    step_1.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.0.produce')
    step_1.add_hyperparameter(name='long_format', argument_type= ArgumentType.VALUE, data=True)
    step_1.add_output('produce')
    pipeline_description.add_step(step_1)

    # Step 2: column parser
    step_2 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_transformation.column_parser.Common'))
    step_2.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.1.produce')
    step_2.add_output('produce')
    pipeline_description.add_step(step_2)

    # Step 3: imputer
    step_3 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_cleaning.imputer.SKlearn'))
    step_3.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.2.produce')
    step_3.add_hyperparameter(name='return_result', argument_type=ArgumentType.VALUE,data='replace')
    step_3.add_hyperparameter(name='use_semantic_types', argument_type=ArgumentType.VALUE,data=True)
    step_3.add_output('produce')
    pipeline_description.add_step(step_3)

    # Step 4,5,6: Distil ensemble classifier
    step_4 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_transformation.extract_columns_by_semantic_types.Common'))
    step_4.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.3.produce')
    step_4.add_output('produce')
    pipeline_description.add_step(step_4)

    step_5 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_transformation.extract_columns_by_semantic_types.Common'))
    step_5.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.3.produce')
    step_5.add_hyperparameter(name='semantic_types', argument_type=ArgumentType.VALUE,data=('https://metadata.datadrivendiscovery.org/types/Target',))
    step_5.add_output('produce')
    pipeline_description.add_step(step_5)

    step_6 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.learner.random_forest.DistilEnsembleForest'))
    step_6.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.4.produce')
    step_6.add_argument(name='outputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.5.produce')
    step_6.add_hyperparameter('metric', ArgumentType.VALUE, metric)
    step_6.add_output('produce')
    pipeline_description.add_step(step_6)

    # Step 13: construct output
    step_7 = PrimitiveStep(primitive=index.get_primitive('d3m.primitives.data_transformation.construct_predictions.Common'))
    step_7.add_argument(name='inputs', argument_type=ArgumentType.CONTAINER, data_reference='steps.6.produce')
    step_7.add_argument(name='reference', argument_type=ArgumentType.CONTAINER, data_reference='steps.3.produce')
    step_7.add_output('produce')
    pipeline_description.add_step(step_7)

    # Final Output
    pipeline_description.add_output(name='output predictions', data_reference='steps.7.produce')

