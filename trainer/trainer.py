import torch
import torch.nn as nn
from torch import Tensor
import wandb
from torch.nn import functional as F
from metrics import perplexity
from utils import create_non_special_mask
from generate import generate_argmax
import pandas as pd
from tqdm import tqdm
class Trainer():
    def __init__(self, model, tokenizer, optimizer, scheduler, train_dataloader, val_dataloader, total_steps, validate_every, save_checkpoint_every, epochs):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  
        self.model = model.to(self.device)
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.criterion = nn.CrossEntropyLoss()
        self.train_dataloader = train_dataloader
        self.val_dataloader = val_dataloader
        self.total_steps = total_steps
        self.validate_every = validate_every
        self.save_checkpoint_every = save_checkpoint_every
        self.epochs = epochs
        self.tokenizer = tokenizer

    def step(self, inputs, lengths, train):
        inputs = inputs.to(self.device)
        
        if train:
            self.optimizer.zero_grad()
        logits = self.model(inputs, lengths)
        mask = torch.arange(logits.size(1)).expand(len(logits), logits.size(1)) < lengths.unsqueeze(1)
        mask = mask.to(self.device)
        perpl = perplexity(inputs, logits, mask)
        loss = self.criterion(logits[:, :-1, :].reshape(-1, logits.shape[-1]), inputs[:, 1:].reshape(-1,))
        loss = loss * mask[:, 1:].contiguous().view(-1).float() 
        total_loss = loss.sum()
        total_non_eos = mask[:, 1:].sum()
        total_loss = total_loss / total_non_eos
        if train:
            total_loss.backward()
            self.optimizer.step()
            self.scheduler.step()
        
        return total_loss.item(), perpl

    def validate(self):
        self.model.eval()
        total_loss = 0
        total_samples = 0
        total_perpl = 0
        
        with torch.no_grad():
            for data in self.val_dataloader:
                inputs, lengths = data
                loss, perpl = self.step(inputs, lengths, False)
                total_perpl += perpl
                total_loss += loss * inputs.size(0)
                total_samples += inputs.size(0)
        
        self.model.train()
        return total_loss / total_samples, total_perpl / len(self.val_dataloader)
    
    def train(self):
        # Настройка WandB
        wandb.init(project='bhw-llm-tiny')
        wandb.watch(self.model)

        # Обучение
        self.model.train()
        step = 0
        for epoch in range(self.epochs):
            for inputs, lengths in tqdm(self.train_dataloader):
                if step >= self.total_steps:
                    break
                
                loss, perpl = self.step(inputs, lengths, True)
                
                if step % self.validate_every == 0:
                    val_loss, val_perpl = self.validate()

                    wandb.log({"Validation Loss": val_loss})
                    wandb.log({"Validation Perplexity": val_perpl})
                    self.log_predictions(10)
                
                if step % self.save_checkpoint_every == 0:
                    torch.save(self.model.state_dict(), f"checkpoint_{step}.pt")

                if step % 50 == 0:  # Логгирование каждые 50 шагов
                    wandb.log({"Training Loss": loss})
                    wandb.log({"Training Perplexity": perpl})
                    for name, param in self.model.named_parameters():
                        wandb.log({f"Model Parameter {name}": param.clone().cpu().detach().numpy()})

                step += 1

        wandb.finish() 

    def log_predictions(self, num):
        inputs, _ = next(iter(self.val_dataloader))
        inputs = inputs[:num, :7].to(self.device)
        argmax_text = self.tokenizer.decode(generate_argmax(self.model, self.tokenizer, self.device, num, prefix=inputs, max_len=32).cpu().numpy().tolist())
        data = {'Texts': argmax_text}
        df = pd.DataFrame(data)
        wandb.log({"Argamx Texts": wandb.Table(dataframe=df)})