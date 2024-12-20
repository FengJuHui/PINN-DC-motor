from ze import *
import os
import random
import matplotlib.pyplot as plt
from tqdm import tqdm


if __name__ == "__main__":
    set_cuda()
    SAVE_DIR, SAVE_DIR_GIF = save_paths()
    DATA_DIR = r"C:\Users\jedua\Documents\INSA\Python\PINN\DC_SCRATCH"

    # Control Variables
    N_training = 1000
    N_data = int(1.2*N_training)
    iterations = 200
    random.seed(0)
    torch.manual_seed(123)
    infe = 1.5
    supe = 1.5
    lambda1 = 10**2
    T_TEST = 4000
    figs = 99
    NOISE = 0.00/100.0 # 0.01 % 
 
    inputs = {  "J":0.1,
                "b":0.5,
                "Kt":1.,
                "L":1.,
                "R":5.,
                "Ke":1.,
                "dt": 1.0*10**-3,
                "Tfinal": 5.,
                "dist_intensity": 1.0*10**-3,
                "SNR": 40} # In dB of maximum amplitude 
    outputs =['time', 'input', 'output']

    # Initial points for constants
    guess = [inputs['J'] + random.uniform(-infe*inputs['J'], supe*inputs['J']),
            inputs['b'] + random.uniform(-infe*inputs['b'], supe*inputs['b']),
            inputs['Kt'] + random.uniform(-infe*inputs['Kt'], supe*inputs['Kt']),
            inputs['L'] + random.uniform(-infe*inputs['L'], supe*inputs['L']),
            inputs['R'] + random.uniform(-infe*inputs['R'], supe*inputs['R']),
            inputs['Ke'] + random.uniform(-infe*inputs['Ke'], supe*inputs['Ke'])]

    # Get exact solution
    X_star, u_star, lb, ub = initialize_from_file(os.path.join(DATA_DIR,"DC_simulation.mat"))

    # Observed noisy dataset (DATA LOSS)
    ind = np.random.choice(range(X_star.shape[0]), N_data, replace=False).astype(int)
    t_obs_np =  X_star[ind,0]
    t_obs =  torch.tensor(t_obs_np, dtype = torch.float).view(-1,1)
    u_obs = torch.tensor(u_star[ind,:]) + NOISE*torch.randn_like(torch.tensor(u_star[ind,:]))

    # define training points over the entire domain (PHYSICS LOSS)
    idx = np.round(np.linspace(0, X_star.shape[0] - 1, N_training)).astype(int)
    t_physics_np = X_star[idx,0]
    t_physics = torch.tensor(t_physics_np, dtype = torch.float).view(-1,1).requires_grad_(True)

    # PUTTING W_pert and V_in AS A KNWON CONSTANT VALUE:
    V_in = torch.tensor(X_star[idx,1])
    W_pert = torch.tensor(X_star[idx,2])

    # For validation
    idc = np.round(np.linspace(0, int(inputs['Tfinal']), T_TEST)).astype(int)
    t_test = torch.tensor(X_star[idc,0], dtype = torch.float).view(-1,1)
    t_test_np = X_star[idc,0]
    u_test_star = torch.tensor(u_star[idc,:])

    # define a neural network to train
    # N_INPUT, N_OUTPUT, N_HIDDEN, N_LAYERS
    pinn = FCN(1,2,32,3)

    # treat Constants as learnable parameter
    J_nn = torch.nn.Parameter(torch.tensor([guess[0]], requires_grad=True))
    b_nn = torch.nn.Parameter(torch.tensor([guess[1]], requires_grad=True))
    Kt_nn = torch.nn.Parameter(torch.tensor([guess[2]], requires_grad=True))
    L_nn = torch.nn.Parameter(torch.tensor([guess[3]], requires_grad=True))
    R_nn = torch.nn.Parameter(torch.tensor([guess[4]], requires_grad=True))
    Ke_nn = torch.nn.Parameter(torch.tensor([guess[5]], requires_grad=True))

    opt_params = [J_nn, b_nn, Kt_nn, L_nn, R_nn, Ke_nn]
    optimiser = torch.optim.Adam(list(pinn.parameters())+opt_params,lr=1e-3)
    
    files = []
    track_constants = []
    track_losses = []
    for i in tqdm(range(iterations)):
        optimiser.zero_grad()

        # ----------------------------------------- compute physics loss -----------------------------------------
        u_phy_hat = pinn(t_physics)
        w_phy_hat = u_phy_hat[:,0]
        i_phy_hat = u_phy_hat[:,1]

        # dudt = torch.autograd.grad(u_phy_hat, torch.cat((t_physics, t_physics), 1), torch.ones_like(u_phy_hat), create_graph=True)[0]
        # dwdt_phy_hat = dudt[:,0]
        # didt_phy_hat = dudt[:,1]

        # d2udt2 = torch.autograd.grad(dudt, torch.cat((t_physics, t_physics), 1), torch.ones_like(dudt), create_graph=True)[0]
        # d2wdt2_phy_hat = d2udt2[:,0]
        # d2idt2_phy_hat = d2udt2[:,1]

        dwdt_phy_hat = torch.autograd.grad( w_phy_hat, t_physics, 
                                            torch.ones_like(w_phy_hat), 
                                            create_graph=True)[0]
        didt_phy_hat = torch.autograd.grad( i_phy_hat, t_physics, 
                                            torch.ones_like(i_phy_hat), 
                                            create_graph=True)[0]
        d2wdt2_phy_hat = torch.autograd.grad( dwdt_phy_hat, t_physics, 
                                            torch.ones_like(dwdt_phy_hat), 
                                            create_graph=True)[0]

        loss_f = torch.mean((J_nn*d2wdt2_phy_hat + b_nn*dwdt_phy_hat - Kt_nn*i_phy_hat + W_pert)**2)
        loss_g = torch.mean((L_nn*didt_phy_hat + Ke_nn*dwdt_phy_hat + R_nn*i_phy_hat - V_in)**2)
        loss1 = loss_f+loss_g

        # ----------------------------------------- compute data loss -----------------------------------------
        u_obs_hat = pinn(t_obs)
        loss2 = torch.mean((u_obs_hat - u_obs)**2)
        
        # ----------------------------------------- compute total loss -----------------------------------------
        loss = loss1 + lambda1*loss2

        u_test = pinn(t_test)
        test_loss = torch.mean((u_test-u_test_star)**2)

        track_constants.append([
                                    J_nn.item(),
                                    b_nn.item(),
                                    Kt_nn.item(),
                                    L_nn.item(),
                                    R_nn.item(),
                                    Ke_nn.item()])

        track_losses.append([
                                loss_f.item(),
                                loss_g.item(),
                                loss2.item(),
                                loss.item(),
                                test_loss.item()])

        # backpropagate joint loss, take optimiser step
        loss.backward()
        optimiser.step()

        # plot the result as training progresses
        if i % figs == 0:

            t_test = torch.linspace(0,int(inputs['Tfinal']),T_TEST).view(-1,1)
            u_test = pinn(t_test).detach()

            # plt.plot(t_test[:,0].detach().cpu().numpy(), u_test[:,1].detach().cpu().numpy())
            # plt.scatter(t_obs[:,0].detach().cpu().numpy(), u_obs[:,0].detach().cpu().numpy(), label="Speed noisy observations", alpha=0.6)
            # plt.show()

            fig, ax = plt.subplots(2,1)
            fig.set_size_inches(18.5, 10.5)
            fig.suptitle(f"Observations and PINN approximation at iter: {i}")
            plt.subplot(2,1,1)
            plt.scatter(t_obs[:,0].detach().cpu().numpy(), u_obs[:,0].detach().cpu().numpy(), label="Speed noisy observations", alpha=0.6)
            plt.plot(t_test[:,0].detach().cpu().numpy(), u_test[:,0].detach().cpu().numpy(), label="PINN solution", color="tab:green")
            plt.legend()

            plt.subplot(2,1,2)
            plt.scatter(t_obs[:,0].detach().cpu().numpy(), u_obs[:,1].detach().cpu().numpy(), label="Current noisy observations", alpha=0.6)
            plt.plot(t_test[:,0].detach().cpu().numpy(), u_test[:,1].detach().cpu().numpy(), label="PINN solution", color="tab:green")
            plt.legend()

            file = os.path.join(SAVE_DIR_GIF,"pinn_%.8i.png"%(i+1))
            fig.savefig(file, dpi=100, facecolor="white")
            files.append(file)
            plt.close(fig)

        if i == 0:
            t_test = torch.linspace(0,int(inputs['Tfinal']),T_TEST).view(-1,1)
            u_test = pinn(t_test).detach()
            save_plotly(i, X_star, u_star, t_obs, u_obs, t_test, u_test,SAVE_DIR)

        if i == iterations-1:
            t_test = torch.linspace(0,int(inputs['Tfinal']),T_TEST).view(-1,1)
            u_test = pinn(t_test).detach()
            save_plotly(i, X_star, u_star, t_obs, u_obs, t_test, u_test,SAVE_DIR)

            # TODO
            # Plot all final values of the equations and check its loss 

    print("\n\nGenerating Loss graphs...\n\n")
    generate_training_figures(inputs, track_constants, track_losses, SAVE_DIR)

    print("\n\nGenerating GIFs...\n\n")
    save_gif_PIL(os.path.join(SAVE_DIR,"learning.gif"), files, fps=60, loop=0)


