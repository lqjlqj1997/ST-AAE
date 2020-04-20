#!/usr/bin/env python
# pylint: disable=W0201
import sys
# sys.path.extend(['../'])

import argparse
import yaml
import numpy as np

# torch
import torch
import torch.nn as nn
import torch.optim as optim

# torchlight
import torchlight
from torchlight import str2bool
from torchlight import DictAction
from torchlight import import_class

from .processor import Processor
import torch.nn.functional as F

def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv1d') != -1:
        m.weight.data.normal_(0.0, 0.02)
        if m.bias is not None:
            m.bias.data.fill_(0)
    elif classname.find('Conv2d') != -1:
        m.weight.data.normal_(0.0, 0.02)
        if m.bias is not None:
            m.bias.data.fill_(0)
    elif classname.find('BatchNorm') != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)
     


    

def loss_function(recon_x, x, mu, logvar):
    n = recon_x.size(0)
    # print(recon_x.shape)
    # BCE = F.binary_cross_entropy(recon_x.view(n,-1), x.view(n,-1), reduction='sum')
    BCE = nn.functional.mse_loss(recon_x, x)
    # print("BCE : ", BCE)
    # see Appendix B from VAE paper:
    # Kingma and Welling. Auto-Encoding Variational Bayes. ICLR, 2014
    # https://arxiv.org/abs/1312.6114
    # 0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
    # print(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(),1).mean())
    # print(mu.pow(2).shape)
    
    KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp(),1).mean()
    return BCE + KLD

class REC_Processor(Processor):
    """
        Processor for Skeleton-based Action Recgnition
    """

    def load_model(self):
        self.model = self.io.load_model(self.arg.model,
                                        **(self.arg.model_args))
        self.model.apply(weights_init)
        self.loss = nn.CrossEntropyLoss()
        
    def load_optimizer(self):
        if self.arg.optimizer == 'SGD':
            self.optimizer = optim.SGD(
                self.model.parameters(),
                lr=self.arg.base_lr,
                momentum=0.9,
                nesterov=self.arg.nesterov,
                weight_decay=self.arg.weight_decay)
        elif self.arg.optimizer == 'Adam':
            self.optimizer = optim.Adam(
                self.model.parameters(),
                lr=self.arg.base_lr,
                weight_decay=self.arg.weight_decay)
        else:
            raise ValueError()

    def adjust_lr(self):
        if self.arg.optimizer == 'SGD' and self.arg.step:
            lr = self.arg.base_lr * (
                0.1**np.sum(self.meta_info['epoch']>= np.array(self.arg.step)))
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = lr
            self.lr = lr
        else:
            self.lr = self.arg.base_lr

    def show_topk(self, k):
        rank = self.result.argsort()
        hit_top_k = [l in rank[i, -k:] for i, l in enumerate(self.label)]
        accuracy = sum(hit_top_k) * 1.0 / len(hit_top_k)
        self.io.print_log('\tTop{}: {:.2f}%'.format(k, 100 * accuracy))

    def train(self):
        self.model.train()
        self.adjust_lr()
        loader = self.data_loader['train']
        loss_value = []
        pred_loss_value = []

        prediciton_loss = nn.NLLLoss()

        for data, label in loader:

            # get data
            data = data.float().to(self.dev)
            label = label.long().to(self.dev)

            # forward
            recon_data, mean, lsig, z = self.model(data)
            loss = loss_function(recon_data, data, mean, lsig)
            
            # backward
            self.optimizer.zero_grad()
            loss.backward()
            self.model.decoder.zero_grad()
            self.optimizer.step()

            #classifier
            prediction = self.model.fc(mean)
            pred_loss = prediciton_loss(prediction,label)

            self.optimizer.zero_grad()
            pred_loss.backward()
            self.model.decoder.zero_grad()
            self.optimizer.step()


            # statistics
            self.iter_info['loss'] = loss.data.item()
            self.iter_info['Pred_loss'] = pred_loss.data.item()
            self.iter_info['lr'] = '{:.6f}'.format(self.lr)
            
            loss_value.append(self.iter_info['loss'])

            pred_loss_value.append(self.iter_info['Pred_loss'])
            
            self.show_iter_info()
            self.meta_info['iter'] += 1

        self.epoch_info['mean_loss']= np.mean(loss_value)
        self.epoch_info['pred_mean_loss']= np.mean(pred_loss_value)

        self.show_epoch_info()
        self.io.print_timer()

    def test(self, evaluation=True):

        self.model.eval()
        loader = self.data_loader['train']
        loss_value = []
        result_frag = []
        label_frag = []

        for data, label in loader:
                    
            # get data
            data = data.float().to(self.dev)
            label = label.long().to(self.dev)

            # inference
            with torch.no_grad():
                recon_data, mean, lsig, z = self.model(data)
            # result_frag.append(recon_data.data.cpu().numpy())

            # get loss
            if evaluation:
                loss = loss_function(recon_data,data,mean,lsig)
                loss_value.append(loss.item())
                # label_frag.append(label.data.cpu().numpy())

        # self.result = np.concatenate(result_frag)
        if evaluation:
            # self.label = np.concatenate(label_frag)
            self.epoch_info['mean_loss']= np.mean(loss_value)
            self.show_epoch_info()

            # show top-k accuracy
            # for k in self.arg.show_topk:
            #     self.show_topk(k)

    @staticmethod
    def get_parser(add_help=False):

        # parameter priority: command line > config > default
        parent_parser = Processor.get_parser(add_help=False)
        parser = argparse.ArgumentParser(
            add_help=add_help,
            parents=[parent_parser],
            description='Spatial Temporal Graph Convolution Network')

        # region arguments yapf: disable
        # evaluation
        parser.add_argument('--show_topk', type=int, default=[1, 5], nargs='+', help='which Top K accuracy will be shown')
        # optim
        parser.add_argument('--base_lr', type=float, default=0.01, help='initial learning rate')
        parser.add_argument('--step', type=int, default=[], nargs='+', help='the epoch where optimizer reduce the learning rate')
        parser.add_argument('--optimizer', default='SGD', help='type of optimizer')
        parser.add_argument('--nesterov', type=str2bool, default=True, help='use nesterov or not')
        parser.add_argument('--weight_decay', type=float, default=0.0001, help='weight decay for optimizer')
        # endregion yapf: enable

        return parser


