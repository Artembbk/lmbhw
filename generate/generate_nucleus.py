import torch
from torch import Tensor
from torch.nn import functional as F

@torch.no_grad()
def generate_nucleus(model, tokenizer, device, batch_size: int, prefix: Tensor = None, max_len=100, nucleus=0.9):
    """
    Samples output sequence from probability distribution obtained by model

    :params
        model: predict next token for the whole batch of sequences
        tokenizer: tokenizer for the model and [BOS] token
        batch_size: number of sequence
        prefix: Tensor of tokens with shape: [batch_size, seq_len]
        max_len: max length of predicted sequence
        nucleus: parameter of nucleus sampling

    :return
        the Tensor of tokens of shape: [batch_size, max_len]
    """
    
    if prefix is None:
        prefix = torch.empty((batch_size, 1), dtype=torch.int32).to(device)
        prefix[:, :] = tokenizer.token_to_id("[BOS]")
    
    while prefix.size(1) < max_len:
        logits = model(prefix)
        logits = logits[:, -1, :].squeeze(1)
        probs = F.softmax(logits, dim=-1)
        sorted_probs, sorted_inds = torch.sort(probs, descending=True, dim=-1)
        cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
        below_nucleus = cumulative_probs < nucleus
        
        if not below_nucleus.any():
            break
            
        selected_indices = sorted_inds[below_nucleus]
        
        # Select from reduced distribution
        next_token = selected_indices[0] if selected_indices.numel() == 1 else torch.multinomial(torch.ones_like(probs), 1)
        prefix = torch.cat([prefix, next_token], dim=-1)
        
    end = torch.empty((batch_size, 1), dtype=torch.int32).to(device)
    end[:, :] = tokenizer.token_to_id("[EOS]")
    prefix = torch.cat((prefix, end), dim=1)
    return prefix