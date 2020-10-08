import logging

from tempfile import TemporaryDirectory
from pathlib import Path

from pytorch_lightning import Callback
import torch.onnx

try:
    import onnx
except ModuleNotFoundError:
    onnx = None

try:
    import onnx_tf.backend as tf_backend
except ModuleNotFoundError:
    tf_backend = None

try:
    import onnxruntime.backend as onnxrt_backend
except ModuleNotFoundError:
    onnxrt_backend = None


def symbolic_batch_dim(model):
    sym_batch_dim = "N"

    inputs = model.graph.input
    for input in inputs:
        dim1 = input.type.tensor_type.shape.dim[0]
        dim1.dim_param = sym_batch_dim


class InferenceBackendBase(Callback):
    """ Base class to run val and test on a backend inference engine """

    def __init__(self, val_batches=1, test_batches=1, val_frequency=10):
        self.test_batches = test_batches
        self.val_batches = val_batches
        self.val_frequency = val_frequency
        self.validation_epoch = 0

    def run_batch(self, batch):
        raise NotImplementedError("run_batch is an abstract method")

    def prepare(self, module):
        raise NotImplementedError("prepare is an abstract method")

    def on_validation_epoch_start(self, trainer, pl_module):
        if self.validation_epoch % self.val_frequency == 0:
            self.prepare(pl_module)

    def on_validation_batch_end(
        self, trainer, pl_module, batch, batch_idx, dataloader_idx
    ):
        if batch_idx < self.val_batches:
            if self.validation_epoch % self.val_frequency == 0:
                result = self.run_batch(inputs=batch)
                target = pl_module.forward(batch[0])

                mse = torch.nn.functional.mse_loss(result[0], target, reduction="mean")
                for logger in pl_module.logger:
                    logger.log_metrics({"val_backend_mse": mse})

    def on_validation_epoch_end(self, trainer, pl_module):
        self.validation_epoch += 1

    def on_test_batch_end(self, trainer, pl_module, batch, batch_idx, dataloader_idx):
        if batch_idx < self.test_batches:
            result = self.run_batch(inputs=batch)


class OnnxTFBackend(InferenceBackendBase):
    """Inference Backend for tensorflow"""

    def __init__(
        self, val_batches=1, test_batches=1, val_frequency=10, use_tf_lite=True
    ):
        super(OnnxTFBackend, self).__init__(
            val_batches=val_batches, test_batches=test_batches, val_frequency=10
        )

        self.tf_model = None
        self.interpreter = None

        if onnx is None or tf_backend is None:
            raise Exception(
                "Could not find required libraries for onnx-tf backend please install with poetry instell -E tf-backend"
            )

    def prepare(self, model):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            logging.info("transfering model to onnx")
            dummy_input = model.example_input_array
            torch.onnx.export(model, dummy_input, tmp_dir / "model.onnx", verbose=False)
            logging.info("Creating tf-protobuf")
            onnx_model = onnx.load(tmp_dir / "model.onnx")
            symbolic_batch_dim(onnx_model)
            self.tf_model = tf_backend.prepare(onnx_model)

    def run_batch(self, inputs):
        logging.info("running tf backend on batch")

        result = self.tf_model.run(inputs=inputs)
        result = [torch.from_numpy(res) for res in result]
        return result


class OnnxruntimeBackend(InferenceBackendBase):
    """Inference Backend for tensorflow"""

    def __init__(
        self, val_batches=1, test_batches=1, val_frequency=10, use_tf_lite=True
    ):
        super(OnnxruntimeBackend, self).__init__(
            val_batches=val_batches, test_batches=test_batches, val_frequency=10
        )

        self.onnxrt_model = None

        if onnx is None or onnxrt_backend is None:
            raise Exception(
                "Could not find required libraries for onnxruntime backend please install with poetry instell -E onnxrt-backend"
            )

    def prepare(self, model):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)

            logging.info("transfering model to onnx")
            dummy_input = model.example_input_array
            torch.onnx.export(model, dummy_input, tmp_dir / "model.onnx", verbose=False)
            logging.info("Creating onnxrt-model")
            onnx_model = onnx.load(tmp_dir / "model.onnx")
            symbolic_batch_dim(onnx_model)
            self.onnxrt_model = onnxrt_backend.prepare(onnx_model)

    def run_batch(self, inputs=None):
        logging.info("running onnxruntime backend on batch")

        result = self.onnxrt_model.run(inputs=[input.numpy() for input in inputs])
        result = [torch.from_numpy(res) for res in result]
        return result


class UltraTrailBackend(InferenceBackendBase):
    def __init__(
        self,
        val_batches=1,
        test_batches=1,
        val_frequency=10,
        use_tf_lite=True,
        ultratrail="",
    ):
        super(OnnxruntimeBackend, self).__init__(
            val_batches=val_batches, test_batches=test_batches, val_frequency=10
        )

        self.acc_dir = Path(ultratrail).absolute()
        backend_file = self.acc_dir / "rtl" / "model" / "memgen.py"
        if not self.backend_file.exists():
            raise Exception(
                f"Could not find ultratrail backend in:  {backend_file} please set --ultratrail to backend path"
            )
        self.memgen = load_module(backend_file)

    def prepare(self, model):
        cfg = self.memgen.translate(model, dummy_input, acc_dir)

    def run_batch(self, inputs=None):
        return True

        test_size = config["hwa_test_size"]
        max_idx = len(test_set)
        idx = random.sample(range(max_idx), test_size)
        inp = [torch.unsqueeze(test_set[i][0], 0) for i in idx]

        out = []
        model.eval()
        with torch.no_grad():
            for i in inp:
                out.append(model(i))

        memgen.generate_test_set(inp, out, acc_dir, cfg.bw_f, cfg.rows)
        memgen.run_inference(
            cfg, acc_dir, inputs="./test_data/inputs/", sim_dir=config["vsim"]
        )
        memgen.read_results(acc_dir, "./test_data/outputs/")
