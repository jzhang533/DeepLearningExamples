# Copyright (c) 2021, NVIDIA CORPORATION. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ctypes
import os

from data_loading.data_module import DataModule
from models.nn_unet import NNUnet
from runtime.args import get_main_args
from runtime.checkpoint import load_model
from runtime.logging import get_logger
from runtime.run import evaluate, export_model, predict, train
from runtime.utils import hvd_init, set_seed, set_tf_flags


def main(args):
    os.environ["TF_GPU_THREAD_MODE"] = "gpu_private"
    os.environ["TF_GPU_THREAD_COUNT"] = "1"

    _libcudart = ctypes.CDLL("libcudart.so")
    # Set device limit on the current device
    # cudaLimitMaxL2FetchGranularity = 0x05
    pValue = ctypes.cast((ctypes.c_int * 1)(), ctypes.POINTER(ctypes.c_int))
    _libcudart.cudaDeviceSetLimit(ctypes.c_int(0x05), ctypes.c_int(128))
    _libcudart.cudaDeviceGetLimit(pValue, ctypes.c_int(0x05))
    assert pValue.contents.value == 128

    hvd_init()
    set_seed(args.seed)
    set_tf_flags(args)
    data = DataModule(args)
    data.setup()

    logger = get_logger(args)
    logger.log_hyperparams(vars(args))

    if args.exec_mode == "train":
        model = NNUnet(args)
        train(args, model, data, logger)
    elif args.exec_mode == "evaluate":
        model = load_model(args)
        evaluate(args, model, data, logger)
    elif args.exec_mode == "predict":
        model = NNUnet(args) if args.benchmark else load_model(args)
        predict(args, model, data, logger)
    elif args.exec_mode == "export":
        # Export model
        model = load_model(args)
        export_model(args, model)
        suffix = "amp" if args.amp else "fp32"
        sm = f"{args.results}/saved_model_task_{args.task}_dim_{args.dim}_" + suffix
        trt = f"{args.results}/trt_saved_model_task_{args.task}_dim_{args.dim}_" + suffix
        args.saved_model_dir = sm if args.load_sm else trt
        args.exec_mode = "evaluate" if args.validate else "predict"

        # Run benchmarking
        model = load_model(args)
        data = DataModule(args)
        data.setup()
        if args.validate:
            evaluate(args, model, data, logger)
        else:
            predict(args, model, data, logger)
    else:
        raise NotImplementedError


if __name__ == "__main__":
    args = get_main_args()
    main(args)
