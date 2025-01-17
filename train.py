from torch.utils.data import DataLoader
import pytorch_lightning as pl
from typing import Optional
from pathlib import Path
import torch
import fire

from model import CLIPCaptionModel, CLIPCaptionPrefixOnly
from dataset import TokenPrefixDataset, MultiplePrefixDataset
from lms import GPT2, GPTJ, T0

class CheckpointSaver(pl.Callback):
    def __init__(self, output_path: Path, filename_prefix: str, save_every_n_epochs: int = 1,
            save_every_n_steps: Optional[int] = 1000):
        output_path.mkdir(exist_ok=True)

        self.output_path = output_path
        self.filename_prefix = filename_prefix
        self.save_every_n_epochs = save_every_n_epochs
        self.save_every_n_steps = save_every_n_steps

    def on_epoch_end(self, trainer: pl.Trainer, _):
        epoch = trainer.current_epoch
        if epoch % self.save_every_n_epochs == 0:
            output_path = self.output_path / f"{self.filename_prefix}_epoch_{epoch}.ckpt"
            trainer.save_checkpoint(output_path)
    
    def on_batch_end(self, trainer: pl.Trainer, _):
        if self.save_every_n_steps is not None:
            current_step = trainer.global_step
            if (current_step % self.save_every_n_steps == 0):
                output_path = self.output_path / f"{self.filename_prefix}_latest.ckpt"
                trainer.save_checkpoint(output_path)
    
    def save_final_checkpoint(self, trainer: pl.Trainer):
        output_path = self.output_path / f"{self.filename_prefix}_final.ckpt"
        trainer.save_checkpoint(output_path)


def train(
    data_dir: str = "./train/",
    output_dir: str = "./models/",
    output_name_prefix: str = "demo_model.ckpt",
    epochs: int = 3,
    save_every_epochs: int = 1,
    save_every_steps: int = 10000,
    scheduler_warmup_steps: int = 500,
    prefix_length: int = 10,
    prefix_size: int = 768,
    clip_prefix_length: int = 10,
    language_model_type = "gpt2",
    language_model_variant = "gpt2-xl",
    batch_size: int = 256,
    prefix_only: bool = False,
    mapping_type: str = "transformer",
    num_layers: int = 8,
    num_attention_heads: int = 8,
    normalize_prefix: bool = False,
    merge_datasets: bool = False,
    use_deepspeed: bool = False,
    use_16bit_precision: bool = True,
    gpu_devices: Optional[str] = "0",
    deepspeed_strategy: Optional[str] = None
):
    """ Starts the main training process. """ # TODO arg docs.

    # Prepare training datasets.
    if merge_datasets:
        data_dirs = data_dir.split(",")

        if len(data_dirs) < 2:
            raise ValueError((
                "--merge_datasets was enabled, but less than 2 directories were specified.\n"
                "You can specify more than one data directory by comma seperating the --data_dir input."
            ))
        
        datasets = []
        for dir in data_dirs:
            datasets.append(
                TokenPrefixDataset(dir, batch_size=batch_size, normalize_prefix=normalize_prefix)
            )
        
        dataset = MultiplePrefixDataset(*datasets)
    else:
        dataset = TokenPrefixDataset(data_dir, batch_size=batch_size, normalize_prefix=normalize_prefix)

    # TODO find better solution for using `get_linear_schedule_with_warmup` with PL.
    total_steps = len(dataset) * epochs

    model_kwargs = {
        "language_model_type": language_model_type,
        "language_model_variant": language_model_variant,
        "prefix_length": prefix_length,
        "clip_prefix_length": clip_prefix_length,
        "prefix_size": prefix_size,
        "num_layers": num_layers,
        "num_attention_heads": num_attention_heads,
        "mapping_type": mapping_type,
        "scheduler_warmup_steps": scheduler_warmup_steps,
        "total_steps": total_steps,
        "use_deepspeed": use_deepspeed
    }

    if prefix_only:
        model = CLIPCaptionPrefixOnly(**model_kwargs)
        print("Train only Prefix.")
    else:
        model = CLIPCaptionModel(**model_kwargs)
        print("Train both Prefix and Language Model.")

    # Easier to use GPU args. `-1` = use all, `0` = use gpu 0, `0,1` = use gpus 1 and 2 etc.
    if isinstance(gpu_devices, int) and gpu_devices != -1:
        gpu_devices = [gpu_devices]
    
    # Create `CheckpointSaver` as a trainer callback instance.
    checkpoint_saver = CheckpointSaver(
        Path(output_dir),
        output_name_prefix,
        save_every_n_epochs=save_every_epochs,
        save_every_n_steps=save_every_steps
    )
    
    # TODO better dataset implementation
    # - Improve dataloader system (batch_size=1 is a temporary fix)
    # - Speed up streaming (multiple workers and/or prepare data ahead of retrieval)
    dataloader = DataLoader(dataset, batch_size=1, shuffle=False)

    # Create trainer class.
    trainer = pl.Trainer(
        gpus=gpu_devices,
        max_epochs=epochs,
        callbacks=[checkpoint_saver],
        strategy=deepspeed_strategy,
        precision=(16 if use_16bit_precision else 32)
    )

    # Run training process.
    trainer.fit(model, dataloader)

    # Save final checkpoint.
    checkpoint_saver.save_final_checkpoint(trainer)


if __name__ == '__main__':
    fire.Fire(train)