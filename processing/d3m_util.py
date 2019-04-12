#!/usr/bin/env python

"""
    d3m_util.py
"""

import sys
import numpy as np

from exline.io import (
    load_ragged_collection,
    load_graph,
    load_graphs,
    load_audio,
    maybe_truncate,
    prep_image_collection,
    load_and_join,
)

from exline.preprocessing.utils import prep_labels
from exline.preprocessing.featurization import DataFrameMapper
from exline.preprocessing.transformers import run_lengths_hist, set2hist, cf_remap_graphs

from exline.modeling.forest import ForestCV
from exline.modeling.neighbors import NeighborsCV
from exline.modeling.sgm import SGMGraphMatcher
from exline.modeling.vertex_nomination import VertexNominationCV
from exline.modeling.collaborative_filtering import SGDCollaborativeFilter
from exline.modeling.link_prediction import RescalLinkPrediction
from exline.modeling.text_classification import TextClassifierCV
from exline.modeling.pretrained_audio import AudiosetModel # !! Slow to import
from exline.modeling.community_detection import CommunityDetection
from exline.modeling.clustering import ClusteringCV
from exline.modeling.fixed_cnn import FixedCNNForest
from exline.modeling.bert_models import BERTPairClassification
from exline.modeling.failure_model import FailureModel

class PreprocessorFunctions:
    """
        Returns Xf_train, Xf_test, U_train (train data, test data, unlabeled train data)
    """

    @staticmethod
    def table(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test = DataFrameMapper(target_metric=ll_metric).pipeline(X_train, X_test, y_train)
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def multitable(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, _ = load_ragged_collection(X_train, X_test, d3mds, collection_type='table')
        Xf_train, Xf_test = set2hist(Xf_train, Xf_test)
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def question_answering(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, _ = load_and_join(X_train, X_test, d3mds)
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def text(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, _ = load_ragged_collection(X_train, X_test, d3mds, collection_type="text")
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def audio(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test = load_audio(X_train, X_test, d3mds)
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def clustering(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        return X_train.copy(), X_test.copy(), None, hparams

    @staticmethod
    def image(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, _ = prep_image_collection(X_train, X_test, d3mds)
        return Xf_train, Xf_test, None, hparams

    @staticmethod
    def graph_matching(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        return X_train.copy(), X_test.copy(), {
            "graphs" : load_graphs(d3mds, n=2)
        }, hparams

    @staticmethod
    def _one_graph(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        return X_train.copy(), X_test.copy(), {
            "graph" : load_graph(d3mds)
        }, hparams

    @staticmethod
    def vertex_nomination(*args, **kwargs):
        return PreprocessorFunctions._one_graph(*args, **kwargs)

    @staticmethod
    def link_prediction(*args, **kwargs):
        return PreprocessorFunctions._one_graph(*args, **kwargs)

    @staticmethod
    def community_detection(*args, **kwargs):
        return PreprocessorFunctions._one_graph(*args, **kwargs)

    @staticmethod
    def timeseries(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, meta_cols = load_ragged_collection(X_train, X_test, d3mds, collection_type="timeseries")

        if (np.hstack(Xf_train) == 0).mean() > 0.5:
            print('!! sparse timeseries', file=sys.stderr)
            Xf_train, Xf_test = run_lengths_hist(Xf_train, Xf_test)
            _ = hparams['metrics'].remove('dtw')

        Xf_train, Xf_test = maybe_truncate(Xf_train, Xf_test)
        return Xf_train, Xf_test, {
            "X_test" : Xf_test,
        }, hparams

    @staticmethod
    def collaborative_filtering(X_train, X_test, y_train, ll_metric, d3mds, hparams):
        Xf_train, Xf_test, n_users, n_items = cf_remap_graphs(X_train, X_test)
        hparams.update({"n_users" : n_users, "n_items" : n_items})
        return Xf_train, Xf_test, None, hparams


model_lookup = {
    "table"                   : ForestCV,
    "multitable"              : ForestCV,
    "question_answering"      : BERTPairClassification,
    "text"                    : TextClassifierCV,
    "audio"                   : AudiosetModel,
    "graph_matching"          : SGMGraphMatcher,
    "vertex_nomination"       : VertexNominationCV,
    "link_prediction"         : RescalLinkPrediction,
    "community_detection"     : CommunityDetection,
    "clustering"              : ClusteringCV,
    "image"                   : FixedCNNForest,
    "timeseries"              : NeighborsCV,
    "collaborative_filtering" : SGDCollaborativeFilter,
}