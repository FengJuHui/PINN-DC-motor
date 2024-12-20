import torch
from torchsummary import summary
# import torchinfo

def set_cuda():
    # CUDA support 
    if torch.cuda.is_available():
        device = torch.device('cuda')
        torch.cuda.set_device(0)
    else:
        device = torch.device('cpu')
    torch.set_default_device(device)

    print(f"\nUsing device: \t**********************\t{device}\t**********************\n\n")

class FCN(torch.nn.Module):
    "Defines a standard fully-connected network in PyTorch"

    def __init__(self, N_INPUT, N_OUTPUT, N_HIDDEN, N_LAYERS, SHOW = False):
        super().__init__()
        activation = torch.nn.Tanh
        self.fcs = torch.nn.Sequential(*[
                        torch.nn.Linear(N_INPUT, N_HIDDEN),
                        activation()])

        self.fch = torch.nn.Sequential(*[
                        torch.nn.Sequential(*[
                            torch.nn.Linear(N_HIDDEN, N_HIDDEN),
                            activation()]) for _ in range(N_LAYERS-1)])

        self.fce = torch.nn.Linear(N_HIDDEN, N_OUTPUT)

        self.network = torch.nn.Sequential(self.fcs,self.fch,self.fce)

        if SHOW:
            summary(self.network,(1,N_INPUT))
        # torchinfo.summary(self.network, (1,N_INPUT))

    # def forward(self, x):
    #     x = self.fcs(x)
    #     x = self.fch(x)
    #     x = self.fce(x)
    #     return x

    def forward(self, x):
        return self.network(x)