from transformers import GPT2Tokenizer as _GPT2Tokenizer
from transformers import GPT2LMHeadModel
from typing import Optional
import torch

class GPT2(GPT2LMHeadModel):
    @classmethod
    def create(cls, model_variant: str = "gpt2-xl", **huggingface_kwargs):
        return cls.from_pretrained(model_variant, **huggingface_kwargs)
    
    def get_embedding_size(self) -> int:
        return self.transformer.wte.weight.shape[1]
    
    def get_embedding_text(self, tokens: torch.Tensor) -> torch.Tensor:
        return self.transformer.wte(tokens)
    
    def call(self, inputs_embeds: Optional[torch.Tensor] = None, labels: Optional[torch.Tensor] = None,
            attention_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        return self(inputs_embeds=inputs_embeds, labels=labels, attention_mask=attention_mask)

class GPT2Tokenizer(_GPT2Tokenizer):
    @classmethod
    def create(cls, model_variant: str = "gpt2-xl", **huggingface_kwargs):
        return cls.from_pretrained(model_variant, **huggingface_kwargs)
    
    def encode_text(self, text: str, truncate: bool = False) -> torch.Tensor:
        return self.encode(text, truncate=truncate)
    
    def decode_tokens(self, tokens: torch.Tensor) -> str:
        return self.decode(tokens)