# #!/usr/bin/env python
# # pylint: disable=W0201
# import sys
# import argparse
# import yaml
# import numpy as np
# import time

# # torch
# import torch
# import torch.nn as nn
# import torch.optim as optim
# from util import import_class

# class Processor():
#     """Processor for Skeleton-based Action Recgnition"""

#     def __init__(self, arg):
#         self.arg = arg
#         self.start_time = self.update_time = time.time()
#         self.save_arg()
#         if arg.phase == 'train':
#             # Added control through the command line
#             arg.train_feeder_args['debug'] = arg.train_feeder_args['debug'] or self.arg.debug
#             logdir = os.path.join(arg.work_dir, 'trainlogs')
#             if not arg.train_feeder_args['debug']:
#                 # logdir = arg.model_saved_name
#                 if os.path.isdir(logdir):
#                     print(f'log_dir {logdir} already exists')
#                     if arg.assume_yes:
#                         answer = 'y'
#                     else:
#                         answer = input('delete it? [y]/n:')
#                     if answer.lower() in ('y', ''):
#                         shutil.rmtree(logdir)
#                         print('Dir removed:', logdir)
#                     else:
#                         print('Dir not removed:', logdir)

#                 self.train_writer = SummaryWriter(os.path.join(logdir, 'train'), 'train')
#                 self.val_writer = SummaryWriter(os.path.join(logdir, 'val'), 'val')
#             else:
#                 self.train_writer = SummaryWriter(os.path.join(logdir, 'debug'), 'debug')

#         self.load_model()
#         self.load_param_groups()
#         self.load_optimizer()
#         self.load_lr_scheduler()
#         self.load_data()

#         self.global_step = 0
#         self.lr = self.arg.base_lr
#         self.best_acc = 0
#         self.best_acc_epoch = 0

#         if self.arg.half:
#             self.print_log('*************************************')
#             self.print_log('*** Using Half Precision Training ***')
#             self.print_log('*************************************')
#             self.model, self.optimizer = apex.amp.initialize(
#                 self.model,
#                 self.optimizer,
#                 opt_level=f'O{self.arg.amp_opt_level}'
#             )
#             if self.arg.amp_opt_level != 1:
#                 self.print_log('[WARN] nn.DataParallel is not yet supported by amp_opt_level != "O1"')

#         if type(self.arg.device) is list:
#             if len(self.arg.device) > 1:
#                 self.print_log(f'{len(self.arg.device)} GPUs available, using DataParallel')
#                 self.model = nn.DataParallel(
#                     self.model,
#                     device_ids=self.arg.device,
#                     output_device=self.output_device
#                 )

#     def load_model(self):
#         output_device = self.arg.device[0] if type(
#             self.arg.device) is list else self.arg.device
#         self.output_device = output_device
#         Model = import_class(self.arg.model)

#         # Copy model file and main
#         shutil.copy2(inspect.getfile(Model), self.arg.work_dir)
#         shutil.copy2(os.path.join('.', __file__), self.arg.work_dir)

#         self.model = Model(**self.arg.model_args).cuda(output_device)
#         self.loss = nn.CrossEntropyLoss().cuda(output_device)
#         self.print_log(f'Model total number of params: {count_params(self.model)}')

#         if self.arg.weights:
#             try:
#                 self.global_step = int(arg.weights[:-3].split('-')[-1])
#             except:
#                 print('Cannot parse global_step from model weights filename')
#                 self.global_step = 0

#             self.print_log(f'Loading weights from {self.arg.weights}')
#             if '.pkl' in self.arg.weights:
#                 with open(self.arg.weights, 'r') as f:
#                     weights = pickle.load(f)
#             else:
#                 weights = torch.load(self.arg.weights)

#             weights = OrderedDict(
#                 [[k.split('module.')[-1],
#                   v.cuda(output_device)] for k, v in weights.items()])

#             for w in self.arg.ignore_weights:
#                 if weights.pop(w, None) is not None:
#                     self.print_log(f'Sucessfully Remove Weights: {w}')
#                 else:
#                     self.print_log(f'Can Not Remove Weights: {w}')

#             try:
#                 self.model.load_state_dict(weights)
#             except:
#                 state = self.model.state_dict()
#                 diff = list(set(state.keys()).difference(set(weights.keys())))
#                 self.print_log('Can not find these weights:')
#                 for d in diff:
#                     self.print_log('  ' + d)
#                 state.update(weights)
#                 self.model.load_state_dict(state)

#     def load_param_groups(self):
#         """
#         Template function for setting different learning behaviour
#         (e.g. LR, weight decay) of different groups of parameters
#         """
#         self.param_groups = defaultdict(list)

#         for name, params in self.model.named_parameters():
#             self.param_groups['other'].append(params)

#         self.optim_param_groups = {
#             'other': {'params': self.param_groups['other']}
#         }

#     def load_optimizer(self):
#         params = list(self.optim_param_groups.values())
#         if self.arg.optimizer == 'SGD':
#             self.optimizer = optim.SGD(
#                 params,
#                 lr=self.arg.base_lr,
#                 momentum=0.9,
#                 nesterov=self.arg.nesterov,
#                 weight_decay=self.arg.weight_decay)
#         elif self.arg.optimizer == 'Adam':
#             self.optimizer = optim.Adam(
#                 params,
#                 lr=self.arg.base_lr,
#                 weight_decay=self.arg.weight_decay)
#         else:
#             raise ValueError('Unsupported optimizer: {}'.format(self.arg.optimizer))

#         # Load optimizer states if any
#         if self.arg.checkpoint is not None:
#             self.print_log(f'Loading optimizer states from: {self.arg.checkpoint}')
#             self.optimizer.load_state_dict(torch.load(self.arg.checkpoint)['optimizer_states'])
#             current_lr = self.optimizer.param_groups[0]['lr']
#             self.print_log(f'Starting LR: {current_lr}')
#             self.print_log(f'Starting WD1: {self.optimizer.param_groups[0]["weight_decay"]}')
#             if len(self.optimizer.param_groups) >= 2:
#                 self.print_log(f'Starting WD2: {self.optimizer.param_groups[1]["weight_decay"]}')

#     def load_lr_scheduler(self):
#         self.lr_scheduler = MultiStepLR(self.optimizer, milestones=self.arg.step, gamma=0.1)
#         if self.arg.checkpoint is not None:
#             scheduler_states = torch.load(self.arg.checkpoint)['lr_scheduler_states']
#             self.print_log(f'Loading LR scheduler states from: {self.arg.checkpoint}')
#             self.lr_scheduler.load_state_dict(scheduler_states)
#             self.print_log(f'Starting last epoch: {scheduler_states["last_epoch"]}')
#             self.print_log(f'Loaded milestones: {scheduler_states["last_epoch"]}')

#     def load_data(self):
#         Feeder = import_class(self.arg.feeder)
#         self.data_loader = dict()

#         def worker_seed_fn(worker_id):
#             # give workers different seeds
#             return init_seed(self.arg.seed + worker_id + 1)

#         if self.arg.phase == 'train':
#             self.data_loader['train'] = torch.utils.data.DataLoader(
#                 dataset=Feeder(**self.arg.train_feeder_args),
#                 batch_size=self.arg.batch_size,
#                 shuffle=True,
#                 num_workers=self.arg.num_worker,
#                 drop_last=True,
#                 worker_init_fn=worker_seed_fn)

#         self.data_loader['test'] = torch.utils.data.DataLoader(
#             dataset=Feeder(**self.arg.test_feeder_args),
#             batch_size=self.arg.test_batch_size,
#             shuffle=False,
#             num_workers=self.arg.num_worker,
#             drop_last=False,
#             worker_init_fn=worker_seed_fn)

#     def save_arg(self):
#         # save arg
#         arg_dict = vars(self.arg)
#         if not os.path.exists(self.arg.work_dir):
#             os.makedirs(self.arg.work_dir)

#         with open(os.path.join(self.arg.work_dir, 'config.yaml'), 'w') as f:
#             yaml.dump(arg_dict, f)

#     def print_time(self):
#         localtime = time.asctime(time.localtime(time.time()))
#         self.print_log(f'Local current time: {localtime}')

#     def print_log(self, s, print_time=True):
#         if print_time:
#             localtime = time.asctime(time.localtime(time.time()))
#             s = f'[ {localtime} ] {s}'
#         print(s)
#         if self.arg.print_log:
#             with open(os.path.join(self.arg.work_dir, 'log.txt'), 'a') as f:
#                 print(s, file=f)

#     def record_time(self):
#         self.cur_time = time.time()
#         return self.cur_time

#     def split_time(self):
#         split_time = time.time() - self.cur_time
#         self.record_time()
#         return split_time

#     def save_states(self, epoch, states, out_folder, out_name):
#         out_folder_path = os.path.join(self.arg.work_dir, out_folder)
#         out_path = os.path.join(out_folder_path, out_name)
#         os.makedirs(out_folder_path, exist_ok=True)
#         torch.save(states, out_path)

#     def save_checkpoint(self, epoch, out_folder='checkpoints'):
#         state_dict = {
#             'epoch': epoch,
#             'optimizer_states': self.optimizer.state_dict(),
#             'lr_scheduler_states': self.lr_scheduler.state_dict(),
#         }

#         checkpoint_name = f'checkpoint-{epoch}-fwbz{self.arg.forward_batch_size}-{int(self.global_step)}.pt'
#         self.save_states(epoch, state_dict, out_folder, checkpoint_name)

#     def save_weights(self, epoch, out_folder='weights'):
#         state_dict = self.model.state_dict()
#         weights = OrderedDict([
#             [k.split('module.')[-1], v.cpu()]
#             for k, v in state_dict.items()
#         ])

#         weights_name = f'weights-{epoch}-{int(self.global_step)}.pt'
#         self.save_states(epoch, weights, out_folder, weights_name)

#     def train(self, epoch, save_model=False):
#         self.model.train()
#         loader = self.data_loader['train']
#         loss_values = []
#         self.train_writer.add_scalar('epoch', epoch + 1, self.global_step)
#         self.record_time()
#         timer = dict(dataloader=0.001, model=0.001, statistics=0.001)

#         current_lr = self.optimizer.param_groups[0]['lr']
#         self.print_log(f'Training epoch: {epoch + 1}, LR: {current_lr:.4f}')

#         process = tqdm(loader, dynamic_ncols=True)
#         for batch_idx, (data, label, index) in enumerate(process):
#             self.global_step += 1
#             # get data
#             with torch.no_grad():
#                 data = data.float().cuda(self.output_device)
#                 label = label.long().cuda(self.output_device)
#             timer['dataloader'] += self.split_time()

#             # backward
#             self.optimizer.zero_grad()

#             ############## Gradient Accumulation for Smaller Batches ##############
#             real_batch_size = self.arg.forward_batch_size
#             splits = len(data) // real_batch_size
#             assert len(data) % real_batch_size == 0, \
#                 'Real batch size should be a factor of arg.batch_size!'

#             for i in range(splits):
#                 left = i * real_batch_size
#                 right = left + real_batch_size
#                 batch_data, batch_label = data[left:right], label[left:right]

#                 # forward
#                 output = self.model(batch_data)
#                 if isinstance(output, tuple):
#                     output, l1 = output
#                     l1 = l1.mean()
#                 else:
#                     l1 = 0

#                 loss = self.loss(output, batch_label) / splits

#                 if self.arg.half:
#                     with apex.amp.scale_loss(loss, self.optimizer) as scaled_loss:
#                         scaled_loss.backward()
#                 else:
#                     loss.backward()

#                 loss_values.append(loss.item())
#                 timer['model'] += self.split_time()

#                 # Display loss
#                 process.set_description(f'(BS {real_batch_size}) loss: {loss.item():.4f}')

#                 value, predict_label = torch.max(output, 1)
#                 acc = torch.mean((predict_label == batch_label).float())

#                 self.train_writer.add_scalar('acc', acc, self.global_step)
#                 self.train_writer.add_scalar('loss', loss.item() * splits, self.global_step)
#                 self.train_writer.add_scalar('loss_l1', l1, self.global_step)

#             #####################################

#             # torch.nn.utils.clip_grad_norm_(self.model.parameters(), 2)
#             self.optimizer.step()

#             # statistics
#             self.lr = self.optimizer.param_groups[0]['lr']
#             self.train_writer.add_scalar('lr', self.lr, self.global_step)
#             timer['statistics'] += self.split_time()

#             # Delete output/loss after each batch since it may introduce extra mem during scoping
#             # https://discuss.pytorch.org/t/gpu-memory-consumption-increases-while-training/2770/3
#             del output
#             del loss

#         # statistics of time consumption and loss
#         proportion = {
#             k: f'{int(round(v * 100 / sum(timer.values()))):02d}%'
#             for k, v in timer.items()
#         }

#         mean_loss = np.mean(loss_values)
#         num_splits = self.arg.batch_size // self.arg.forward_batch_size
#         self.print_log(f'\tMean training loss: {mean_loss:.4f} (BS {self.arg.batch_size}: {mean_loss * num_splits:.4f}).')
#         self.print_log('\tTime consumption: [Data]{dataloader}, [Network]{model}'.format(**proportion))

#         # PyTorch > 1.2.0: update LR scheduler here with `.step()`
#         # and make sure to save the `lr_scheduler.state_dict()` as part of checkpoint
#         self.lr_scheduler.step()

#         if save_model:
#             # save training checkpoint & weights
#             self.save_weights(epoch + 1)
#             self.save_checkpoint(epoch + 1)

#     def eval(self, epoch, save_score=False, loader_name=['test'], wrong_file=None, result_file=None):
#         # Skip evaluation if too early
#         if epoch + 1 < self.arg.eval_start:
#             return

#         if wrong_file is not None:
#             f_w = open(wrong_file, 'w')
#         if result_file is not None:
#             f_r = open(result_file, 'w')
#         with torch.no_grad():
#             self.model = self.model.cuda(self.output_device)
#             self.model.eval()
#             self.print_log(f'Eval epoch: {epoch + 1}')
#             for ln in loader_name:
#                 loss_values = []
#                 score_batches = []
#                 step = 0
#                 process = tqdm(self.data_loader[ln], dynamic_ncols=True)
#                 for batch_idx, (data, label, index) in enumerate(process):
#                     data = data.float().cuda(self.output_device)
#                     label = label.long().cuda(self.output_device)
#                     output = self.model(data)
#                     if isinstance(output, tuple):
#                         output, l1 = output
#                         l1 = l1.mean()
#                     else:
#                         l1 = 0
#                     loss = self.loss(output, label)
#                     score_batches.append(output.data.cpu().numpy())
#                     loss_values.append(loss.item())

#                     _, predict_label = torch.max(output.data, 1)
#                     step += 1

#                     if wrong_file is not None or result_file is not None:
#                         predict = list(predict_label.cpu().numpy())
#                         true = list(label.data.cpu().numpy())
#                         for i, x in enumerate(predict):
#                             if result_file is not None:
#                                 f_r.write(str(x) + ',' + str(true[i]) + '\n')
#                             if x != true[i] and wrong_file is not None:
#                                 f_w.write(str(index[i]) + ',' + str(x) + ',' + str(true[i]) + '\n')

#             score = np.concatenate(score_batches)
#             loss = np.mean(loss_values)
#             accuracy = self.data_loader[ln].dataset.top_k(score, 1)
#             if accuracy > self.best_acc:
#                 self.best_acc = accuracy
#                 self.best_acc_epoch = epoch + 1

#             print('Accuracy: ', accuracy, ' model: ', self.arg.work_dir)
#             if self.arg.phase == 'train' and not self.arg.debug:
#                 self.val_writer.add_scalar('loss', loss, self.global_step)
#                 self.val_writer.add_scalar('loss_l1', l1, self.global_step)
#                 self.val_writer.add_scalar('acc', accuracy, self.global_step)

#             score_dict = dict(zip(self.data_loader[ln].dataset.sample_name, score))
#             self.print_log(f'\tMean {ln} loss of {len(self.data_loader[ln])} batches: {np.mean(loss_values)}.')
#             for k in self.arg.show_topk:
#                 self.print_log(f'\tTop {k}: {100 * self.data_loader[ln].dataset.top_k(score, k):.2f}%')

#             if save_score:
#                 with open('{}/epoch{}_{}_score.pkl'.format(self.arg.work_dir, epoch + 1, ln), 'wb') as f:
#                     pickle.dump(score_dict, f)

#         # Empty cache after evaluation
#         torch.cuda.empty_cache()

#     def start(self):
#         if self.arg.phase == 'train':
#             self.print_log(f'Parameters:\n{pprint.pformat(vars(self.arg))}\n')
#             self.print_log(f'Model total number of params: {count_params(self.model)}')
#             self.global_step = self.arg.start_epoch * len(self.data_loader['train']) / self.arg.batch_size
#             for epoch in range(self.arg.start_epoch, self.arg.num_epoch):
#                 save_model = ((epoch + 1) % self.arg.save_interval == 0) or (epoch + 1 == self.arg.num_epoch)
#                 self.train(epoch, save_model=save_model)
#                 self.eval(epoch, save_score=self.arg.save_score, loader_name=['test'])

#             num_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
#             self.print_log(f'Best accuracy: {self.best_acc}')
#             self.print_log(f'Epoch number: {self.best_acc_epoch}')
#             self.print_log(f'Model name: {self.arg.work_dir}')
#             self.print_log(f'Model total number of params: {num_params}')
#             self.print_log(f'Weight decay: {self.arg.weight_decay}')
#             self.print_log(f'Base LR: {self.arg.base_lr}')
#             self.print_log(f'Batch Size: {self.arg.batch_size}')
#             self.print_log(f'Forward Batch Size: {self.arg.forward_batch_size}')
#             self.print_log(f'Test Batch Size: {self.arg.test_batch_size}')

#         elif self.arg.phase == 'test':
#             if not self.arg.test_feeder_args['debug']:
#                 wf = os.path.join(self.arg.work_dir, 'wrong-samples.txt')
#                 rf = os.path.join(self.arg.work_dir, 'right-samples.txt')
#             else:
#                 wf = rf = None
#             if self.arg.weights is None:
#                 raise ValueError('Please appoint --weights.')

#             self.print_log(f'Model:   {self.arg.model}')
#             self.print_log(f'Weights: {self.arg.weights}')

#             self.eval(
#                 epoch=0,
#                 save_score=self.arg.save_score,
#                 loader_name=['test'],
#                 wrong_file=wf,
#                 result_file=rf
#             )

#             self.print_log('Done.\n')

#     def show_epoch_info(self):
#         for k, v in self.epoch_info.items():
#             self.io.print_log('\t{}: {}'.format(k, v))
#         if self.arg.pavi_log:
#             self.io.log('train', self.meta_info['iter'], self.epoch_info)

#     def show_iter_info(self):
#         if self.meta_info['iter'] % self.arg.log_interval == 0:
#             info ='\tIter {} Done.'.format(self.meta_info['iter'])
#             for k, v in self.iter_info.items():
#                 if isinstance(v, float):
#                     info = info + ' | {}: {:.4f}'.format(k, v)
#                 else:
#                     info = info + ' | {}: {}'.format(k, v)

#             self.io.print_log(info)

#             if self.arg.pavi_log:
#                 self.io.log('train', self.meta_info['iter'], self.iter_info)

#     def train(self):
#         for _ in range(100):
#             self.iter_info['loss'] = 0
#             self.show_iter_info()
#             self.meta_info['iter'] += 1
#         self.epoch_info['mean loss'] = 0
#         self.show_epoch_info()

#     def test(self):
#         for _ in range(100):
#             self.iter_info['loss'] = 1
#             self.show_iter_info()
#         self.epoch_info['mean loss'] = 1
#         self.show_epoch_info()

#     def start(self):
#         self.io.print_log('Parameters:\n{}\n'.format(str(vars(self.arg))))

#         # training phase
#         if self.arg.phase == 'train':
#             for epoch in range(self.arg.start_epoch, self.arg.num_epoch):
#                 self.meta_info['epoch'] = epoch

#                 # training
#                 self.io.print_log('Training epoch: {}'.format(epoch))
#                 self.train()
#                 self.io.print_log('Done.')

#                 # save model
#                 if ((epoch + 1) % self.arg.save_interval == 0) or (
#                         epoch + 1 == self.arg.num_epoch):
#                     filename = 'epoch{}_model.pt'.format(epoch + 1)
#                     self.io.save_model(self.model, filename)

#                 # evaluation
#                 if ((epoch + 1) % self.arg.eval_interval == 0) or (
#                         epoch + 1 == self.arg.num_epoch):
#                     self.io.print_log('Eval epoch: {}'.format(epoch))
#                     self.test()
#                     self.io.print_log('Done.')
#         # test phase
#         elif self.arg.phase == 'test':

#             # the path of weights must be appointed
#             if self.arg.weights is None:
#                 raise ValueError('Please appoint --weights.')
#             self.io.print_log('Model:   {}.'.format(self.arg.model))
#             self.io.print_log('Weights: {}.'.format(self.arg.weights))

#             # evaluation
#             self.io.print_log('Evaluation Start:')
#             self.test()
#             self.io.print_log('Done.\n')

#             # save the output of model
#             if self.arg.save_result:
#                 result_dict = dict(
#                     zip(self.data_loader['test'].dataset.sample_name,
#                         self.result))
#                 self.io.save_pkl(result_dict, 'test_result.pkl')


