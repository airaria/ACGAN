# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.parallel
import torch.autograd as autograd
import math
from torch.autograd import Variable

import numpy as np 



def gradient_penalty( discriminator , real_sample , fake_sample , num_class ,cuda = False ):
    
    batch = real_sample.shape[0]

    alpha = torch.from_numpy( np.random.random([batch,1,1,1]).astype(np.float32))
    if cuda:
        alpha = alpha.cuda()

    interpolate = (alpha * real_sample.data)  +  ((1.0-alpha) * fake_sample.data)
    interpolate.requires_grad = True
    output  = discriminator(interpolate)
    
    grad_output = ( (torch.empty([batch,1]).fill_(1.0)).requires_grad_(False).cuda() if cuda else\
                    torch.empty([batch,1]).fill_(1.0).requires_grad_(False),\
                    torch.empty([batch, num_class]).fill_(1.0).requires_grad_(False).cuda() if cuda else\
                    torch.empty([batch, num_class]).fill_(1.0).requires_grad_(False)
                    )
    
    #print(grad_output.requires_grad)
    
    #if cuda:
    #    grad_output = grad_output.cuda()
    #grad_output.requires_grad = False

    #print(output.size())
    #print(interpoate.size())
    #print(grad_output.size())

    grads  = autograd.grad( outputs = output, inputs = interpolate, grad_outputs = grad_output,
    create_graph=True,retain_graph=True, only_inputs=True)[0]
    
    grads = grads.view(batch,-1)
    penalty = (grads.norm(p=2 , dim = 1) - 1.0) ** 2
    penalty = torch.mean(penalty)
    return penalty

class Generator( nn.Module ):
    
    def __init__(self , args ):
        super(Generator, self).__init__()
        self.initsize = args.imsize // 16
        self.gfdim = args.gfdim
        
        self.embedding = nn.Embedding( args.num_class , args.dim_embed )
        self.fc1 = nn.Linear( args.dim_embed ,  args.gfdim * 8 )
        
        self.batchnorm_fc = nn.BatchNorm2d(args.gfdim * 16)
        
        if args.deconv:
            
            pad = math.ceil( (args.g_kernel - 2) / 2)
            outpad = -((args.g_kernel - 2) - (2*pad))
            
            self.conv = nn.Sequential(
                    nn.ConvTranspose2d( args.gfdim*8 , args.gfdim * 8 , args.g_kernel ,stride = 1 , padding = 0 , bias = False),
                    nn.BatchNorm2d(args.gfdim * 8),
                    nn.ReLU(inplace = True)
                    )
            self.conv0 = nn.Sequential(
                    nn.ConvTranspose2d(args.gfdim * 16 , args.gfdim * 8 , args.g_kernel ,stride = 2 ,  padding = pad , output_padding = outpad , bias = False),
                    nn.BatchNorm2d(args.gfdim * 8),
                    nn.ReLU(inplace = True)
                    )


    
            
            self.conv1 = nn.Sequential(
                    nn.ConvTranspose2d(args.gfdim * 8 , args.gfdim * 4 , args.g_kernel ,stride = 2 , padding = pad , output_padding = outpad, bias = False ),
                    nn.BatchNorm2d(args.gfdim * 4),
                    nn.ReLU(inplace = True)
                    )
            self.conv2 = nn.Sequential(
                    nn.ConvTranspose2d(args.gfdim * 4 , args.gfdim * 2 , args.g_kernel ,stride = 2 , padding = pad , output_padding = outpad, bias = False ),
                    nn.BatchNorm2d(args.gfdim * 2),
                    nn.ReLU(inplace = True)
                    )
            self.conv3 = nn.Sequential(
                    nn.ConvTranspose2d(args.gfdim * 2 , args.gfdim  , args.g_kernel ,stride = 2 , padding = pad , output_padding = outpad, bias = False ),
                    nn.BatchNorm2d(args.gfdim ),
                    nn.ReLU(inplace = True)
                    )
            self.conv4 = nn.Sequential(
                    nn.ZeroPad2d((1,0,1,0)),
                    nn.Conv2d(args.gfdim , args.out_dim , 4 , stride = 1  , padding = 1 , bias = False),
                    nn.Tanh()
                    )
            self.convDC = nn.Sequential(
                    nn.ConvTranspose2d(args.gfdim  , args.out_dim  , args.g_kernel ,stride = 2 , padding = pad , output_padding = outpad  , bias = False),
                    nn.Tanh()
                    )
        else:
            pad = ((args.g_kernel-1))/2
            self.conv1 = nn.Sequential(
                    nn.Conv2d(args.gfdim * 8 , args.gfdim*4 , 3 , stride = 1 , padding = 1 , bias = False),
                    nn.BatchNorm2d(args.gfdim * 4),
                    nn.LeakyReLU(inplace = True ),
                    nn.Upsample(scale_factor = 2 ),
                    )
            self.conv2 = nn.Sequential(
                    nn.Conv2d(args.gfdim * 4 , args.gfdim*2 , 3  , stride = 1 , padding = 1 , bias = False),
                    nn.BatchNorm2d(args.gfdim * 2),
                    nn.LeakyReLU(inplace = True ),
                     nn.Upsample(scale_factor = 2 ),
                    )
            self.conv3 = nn.Sequential(
                    nn.Conv2d(args.gfdim * 2 , args.gfdim , 3 , stride = 1 , padding = 1, bias = False ),
                    nn.BatchNorm2d(args.gfdim ) ,
                    nn.LeakyReLU(inplace = True ),
                    nn.Upsample(scale_factor = 2 ),
                    )
            self.conv4 = nn.Sequential(
                    nn.ZeroPad2d((1,0,1,0)),
                    nn.Conv2d(args.gfdim , args.out_dim , 4 , stride = 1  , padding = 1, bias = False),
                    nn.Tanh()
                    )
            
        
    def forward(self , noise ,  class_index ):
        #print(noise.shape)
        #print(class_index.shape)
        #latent = self.embedding(class_index)
        #print(latent.shape)
        #x = torch.mul( latent , noise)
        #print(x.shape)
        
        x = noise
        
        x = self.fc1(x)
        #print(x.shape)
        
        #x = x.view( x.shape[0] , self.gfdim * 16 , self.initsize , self.initsize)
        x = x.view( x.shape[0] , self.gfdim * 8 , 1,1)
        #x = self.batchnorm_fc(x)
        #x = self.conv0(x)
        x = self.conv(x)
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x) 
        #x = self.conv4(x)
        x = self.convDC(x)
        
        return x
    

class Discriminator( nn.Module ):
    
    def __init__(self, args ):
        
        super(Discriminator, self).__init__()
        

        if args.sn:
            self.conv1 = nn.Sequential(
                nn.utils.spectral_norm( nn.Conv2d(args.out_dim , args.dfdim , 3 , 2 , 1, bias = False )),
                nn.LeakyReLU(inplace= True)
                )
            self.conv2 = nn.Sequential(
                nn.utils.spectral_norm( nn.Conv2d(args.dfdim , args.dfdim*2 , 3 , 2 , 1 , bias = False)),
                nn.LeakyReLU(inplace= True)
                )
            self.conv3 = nn.Sequential(
                nn.utils.spectral_norm( nn.Conv2d(args.dfdim*2 , args.dfdim*4 , 3 , 2 , 1 , bias = False)),
                nn.LeakyReLU(inplace= True)
                )
            self.conv4 = nn.Sequential(
                    nn.ZeroPad2d((1,0,1,0)),
                    nn.utils.spectral_norm(nn.Conv2d(args.dfdim * 4 , args.dfdim * 8  , 4 , stride = 1  , padding = 1, bias = False)),
                    nn.Tanh()
                    )
        else:
            self.conv1 = nn.Sequential(
                nn.Conv2d(args.out_dim, args.dfdim , 3 , 2 ,1 , bias = False),
                nn.LeakyReLU(inplace= True)
                )
            self.conv1 = nn.Sequential(
                nn.Conv2d(args.dfdim, args.dfdim*2 , 3 , 2 ,1 , bias = False),
                nn.BatchNorm2d(args.dfdim *2),
                nn.LeakyReLU(inplace= True)
                )
            self.conv1 = nn.Sequential(
                nn.Conv2d(args.dfdim*2, args.dfdim*4 , 3 , 2 ,1, bias = False ),
                nn.BatchNorm2d(args.dfdim *4 ),
                nn.LeakyReLU(inplace= True)
                )
            self.conv4 = nn.Sequential(
                    nn.ZeroPad2d((1,0,1,0)),
                    nn.Conv2d(args.gdfdim * 4 , args.dfdim * 8  , 4 , stride = 1  , padding = 1, bias = False),
                    nn.Tanh()
                    )
        
        self.dsize = args.imsize // (8)
        self.dfdim = args.dfdim
        
        self.fc_gan = nn.Linear( args.dfdim* 8 * (self.dsize**2) , 1)
        self.fc_aux1 = nn.Linear( args.dfdim* 8 * (self.dsize**2) , 128)
        self.fc_aux2 = nn.Linear( 128 , args.num_class)
        self.fc_aux = nn.Linear(args.dfdim* 8 * (self.dsize**2) , args.num_class)
        
        self.out_dim = args.out_dim
        self.num_class = args.num_class
        self.soft_max = nn.Softmax()
        self.sigmoid = nn.Sigmoid()
    
    def forward(self , _input ):
        x = self.conv1(_input)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = x.view( _input.shape[0] , self.dfdim * 8 * (self.dsize**2) )
        
        gan_out= self.sigmoid(self.fc_gan(x))
        
        #aux_temp = self.fc_aux1(x)
        #aux_out = self.soft_max(self.fc_aux2(aux_temp))
        
        aux_out = self.soft_max(self.fc_aux(x))
        return gan_out , aux_out

