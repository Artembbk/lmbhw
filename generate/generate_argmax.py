import torch
from torch import Tensor

@torch.no_grad()
def generate_argmax(self, model, tokenizer, device, batch_size: int, prefix: Tensor = None, max_len=100):
    """
    Samples output sequence from probability distribution obtained by model.
    if Tensor of prefix is None then full it with [BOS] token

    :params
        model: predict next token for the whole batch of sequences
        tokenizer: tokenizer for the model and [BOS] token
        batch_size: number of sequence
        prefix: Tensor of tokens with shape: [batch_size, seq_len]
        max_len: max length of predicted sequence

    :return
        the Tensor of tokens of shape: [batch_size, max_len + 1]
    """
    
    if prefix is None:
        prefix = torch.empty((batch_size, 1), dtype=torch.int32).to(device)
        prefix[:, :] = tokenizer.token_to_id("[BOS]")
    
    while prefix.size(1) < max_len:
        inds = model.get_next_token(prefix).argmax(1, keepdim=True)
        prefix = torch.cat((prefix, inds), dim=1)
        
    end = torch.empty((batch_size, 1), dtype=torch.int32).to(device)
    end[:, :] = tokenizer.token_to_id("[EOS]")
    prefix = torch.cat((prefix, end), dim=1)
    return prefix