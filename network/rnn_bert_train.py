from __future__ import print_function
#%matplotlib inline
import argparse
import os
import random
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torch.utils.data
import torchvision.datasets as dset
import torchvision.transforms as transforms
import torchvision.utils as vutils
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import rnn_char_net
import time
import utility
import torch.nn.functional as F

# Train the network on a single character sequence
def train_batch(net, criterion, optimizer, input_seq_tensor, target_seq_tensor, hidden):
	net.zero_grad()
	optimizer.zero_grad()

	loss = 0
	# Loop through each vec in the sequence
	for i in range(input_seq_tensor.size(0)):
		output, hidden = net(input_seq_tensor[i], hidden)
		output = F.normalize(output, dim=1)
		l = criterion(output, target_seq_tensor[i].unsqueeze(0), torch.tensor(1))
		loss += l

	loss.backward()
	optimizer.step()

	return output, loss.item(), hidden.detach()

def train_net(net, criterion, optimizer, data, n_hidden, seq_length, n_epochs, learning_rate, device):
	print("Training progress: ")
	smooth_loss = 0
	smooth_interpolation_rate = 0.02
	smooth_loss_vec = []
	loss_vec = []
	# Current inner loop iteration (total)
	current_iteration = 0
	expected_number_of_iterations = (data.vec_data.size(0) / seq_length) * n_epochs    # (approximative)

	start_time = time.time()

	# One epoch = one full run through the training data (such as goblet_book.txt)
	for epoch in range(n_epochs):
		i=0
		hidden = net.initHidden(device)
		# One iteration = one sequence of text data (such as 25 characters)
		while i < (data.vec_data.size(0) - seq_length):
			X = data.vec_data[i:i+seq_length, :, :]
			Y = data.vec_data[i+1:i+seq_length+1, 0, :]
			output, loss, hidden = train_batch(net, criterion, optimizer, X, Y, hidden)
			if current_iteration == 0:
				smooth_loss = loss
			else:
				smooth_loss = smooth_loss * (1 - smooth_interpolation_rate) + loss * smooth_interpolation_rate
			
			percent_done = round((current_iteration / expected_number_of_iterations) * 100)
			if current_iteration % 10 == 0:
				print("\t" + str(percent_done) + " % done. Smooth loss: " +  str("{:.2f}").format(smooth_loss), end="\r")
			i += seq_length
			current_iteration += 1
			loss_vec.append(loss)
			smooth_loss_vec.append(smooth_loss)

	total_time = time.time() - start_time
	print("\t100% done. Smooth loss: " +  str("{:.2f}").format(smooth_loss))
	print()
	print("Total training time: " + str(round(total_time)) + " seconds")

	return loss_vec, smooth_loss_vec

def synthesize_words(data, net, n, device):
	hidden = net.initHidden(device)
	net.zero_grad()
	prev_vec = data.vec_data[0]
	vecs = torch.empty(n, data.K)
	ids = [None]*n
	for i in range(n):
		output, hidden = net(prev_vec, hidden)
		output = F.normalize(output, dim=1)
		vecs[i], ids[i] = data.veclike2vec(output)
		prev_vec = vecs[i].unsqueeze(0)
	words = data.tokenizer.decode(ids)
	return words