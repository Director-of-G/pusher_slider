## Author: Joao Moura
## Date: 21/08/2020
#  -------------------------------------------------------------------
## Description:
#  This script implements a non-linear program (NLP) model predictive controller (MPC)
#  for tracking a trajectory of a square slider object with a single
#  and sliding contact pusher.
#  -------------------------------------------------------------------

## Import Libraries
#  -------------------------------------------------------------------
import sys
import numpy as np
import casadi as cs
# import casadi
import matplotlib.pyplot as plt
plt.rcParams['figure.dpi'] = 150
import matplotlib.animation as animation
#  -------------------------------------------------------------------
import sliding_pack
#  -------------------------------------------------------------------

# Set Problem constants
#  -------------------------------------------------------------------
a = 0.09 # side dimension of the square slider in meters
T = 12 # time of the simulation is seconds
freq = 25 # number of increments per second
r_pusher = 0.01 # radius of the cylindrical pusher in meter
miu_p = 0.4  # friction between pusher and slider
# N_MPC = 12 # time horizon for the MPC controller
N_MPC = 25 # time horizon for the MPC controller
x_init_val = [-0.01, 0.03, 30*(np.pi/180.), 0]
f_lim = 0.3 # limit on the actuations
psi_dot_lim = 3.0 # limit on the actuations
psi_lim = 40*(np.pi/180.0)
# solver_name = 'ipopt'
solver_name = 'snopt'
# solver_name = 'gurobi'
# solver_name = 'qpoases'
no_printing = True
code_gen = False
show_anim = True
W_x = cs.diag(cs.SX([1.0, 1.0, 0.01, 0.0]))
# contact_mode = 'sliding_contact_mi'
contact_mode = 'sliding_contact_cc'
# contact_mode = 'sticking_contact'
# linDynFlag = True
linDynFlag = False
X_goal = None
# X_goal = [0., 0.5, 40*(np.pi/180.), 0.]
#  -------------------------------------------------------------------
# Computing Problem constants
#  -------------------------------------------------------------------
dt = 1.0/freq # sampling time
N = int(T*freq) # total number of iterations
Nidx = int(N)
# Nidx = 10
#  -------------------------------------------------------------------

# define system dynamics
#  -------------------------------------------------------------------
dyn = sliding_pack.dyn.System_square_slider_quasi_static_ellipsoidal_limit_surface(
        mode=contact_mode,
        slider_dim=a,
        pusher_radious=r_pusher,
        miu=miu_p,
        f_lim=f_lim,
        psi_dot_lim=psi_dot_lim,
        psi_lim=psi_lim
)
#  -------------------------------------------------------------------

# Generate Nominal Trajectory
#  -------------------------------------------------------------------
# x0_nom, x1_nom = sliding_pack.traj.generate_traj_line(X_goal[0], X_goal[1], N, N_MPC)
# x0_nom, x1_nom = sliding_pack.traj.generate_traj_line(0.5, 0.3, N, N_MPC)
# x0_nom, x1_nom = sliding_pack.traj.generate_traj_circle(-np.pi/2, 3*np.pi/2, 0.1, N, N_MPC)
x0_nom, x1_nom = sliding_pack.traj.generate_traj_eight(0.2, N, N_MPC)
#  -------------------------------------------------------------------
# stack state and derivative of state
X_nom_val, _ = sliding_pack.traj.compute_nomState_from_nomTraj(x0_nom, x1_nom, dt)
#  ------------------------------------------------------------------

# Compute nominal actions for sticking contact
#  ------------------------------------------------------------------
dynNom = sliding_pack.dyn.System_square_slider_quasi_static_ellipsoidal_limit_surface(
        mode='sticking_contact',
        slider_dim=a,
        pusher_radious=r_pusher,
        miu=miu_p,
        f_lim=f_lim,
        psi_dot_lim=psi_dot_lim,
        psi_lim=psi_lim
)
W_u = cs.diag(cs.SX([0.1, 0.1]))
optObjNom = sliding_pack.nlp.MPC_nlpClass(
        dynNom, N+N_MPC, W_x, W_u, X_nom_val, dt=dt)
optObjNom.buildProblem('snopt')
resultFlag, X_nom_val_opt, U_nom_val_opt, _, _, _ = optObjNom.solveProblem(
        0, [0., 0., 0., 0.])
U_nom_val_opt = cs.vertcat(
        U_nom_val_opt,
        cs.DM.zeros(dyn.Nu - dynNom.Nu, N+N_MPC-1))
f_d = cs.Function('f_d', [dyn.x, dyn.u], [dyn.x + dyn.f(dyn.x, dyn.u)*dt])
f_rollout = f_d.mapaccum(N+N_MPC-1)
# X_nom_comp = f_rollout([0., 0., 0., 0.], U_nom_val_opt)
#  ------------------------------------------------------------------

# define optimization problem
#  -------------------------------------------------------------------
W_u = cs.diag(cs.SX(dyn.Nu, 1))
optObj = sliding_pack.nlp.MPC_nlpClass(
        dyn, N_MPC, W_x, W_u, X_nom_val, U_nom_val_opt,
        dt=dt,
        linDyn=linDynFlag,
        X_goal=X_goal
)
#  -------------------------------------------------------------------
optObj.buildProblem(solver_name, code_gen, no_printing)
#  -------------------------------------------------------------------

# Initialize variables for plotting
#  -------------------------------------------------------------------
X_plot = np.empty([dyn.Nx, Nidx])
U_plot = np.empty([dyn.Nu, Nidx-1])
del_plot = np.empty([dyn.Nz, Nidx-1])
X_plot[:, 0] = x_init_val
X_future = np.empty([dyn.Nx, N_MPC, Nidx])
comp_time = np.empty(Nidx-1)
success = np.empty(Nidx-1)
cost_plot = np.empty(Nidx-1)
#  -------------------------------------------------------------------

# Set arguments and solve
#  -------------------------------------------------------------------
x0 = x_init_val
# x0 = [0.0, 0.0, 0.0, 0.0]
u0 = [0.0, 0.0, 0.0, 0.0]
for idx in range(Nidx-1):
    print('-------------------------')
    print(idx)
    # ---- solve problem ----
    resultFlag, x_opt, u_opt, del_opt, f_opt, t_opt = optObj.solveProblem(idx, x0)
    # ---- update initial state (simulation) ----
    u0 = u_opt[:, 0].elements()
    # x0 = x_opt[:,1].elements()
    x0 = (x0 + dyn.f(x0, u0)*dt).elements()
    # ---- store values for plotting ----
    comp_time[idx] = t_opt
    success[idx] = resultFlag
    cost_plot[idx] = f_opt
    X_plot[:, idx+1] = x0
    U_plot[:, idx] = u0
    X_future[:, :, idx] = np.array(x_opt)
    if dyn.Nz > 0:
        del_plot[:, idx] = del_opt[:, 0].elements()
#  -------------------------------------------------------------------
# show sparsity pattern
# sliding_pack.plots.plot_sparsity(cs.vertcat(*opt.g), cs.vertcat(*opt.x), xu_opt)
#  -------------------------------------------------------------------

# Animation
#  -------------------------------------------------------------------
if show_anim:
#  -------------------------------------------------------------------
    fig, ax = sliding_pack.plots.plot_nominal_traj(x0_nom[:Nidx], x1_nom[:Nidx])
    # add computed nominal trajectory
    X_nom_val_opt = np.array(X_nom_val_opt)
    ax.plot(X_nom_val_opt[0, :], X_nom_val_opt[1, :], color='blue',
            linewidth=2.0, linestyle='dashed')
    # set window size
    fig.set_size_inches(8, 6, forward=True)
    # get slider and pusher patches
    dyn.set_patches(ax, X_plot)
    # call the animation
    ani = animation.FuncAnimation(
            fig,
            dyn.animate,
            fargs=(ax, X_plot, X_future),
            frames=Nidx-1,
            interval=dt*1000,  # microseconds
            blit=True,
            repeat=False,
    )
    ## to save animation, uncomment the line below:
    # ani.save('MPC_NLP_eight.mp4', fps=25, extra_args=['-vcodec', 'libx264'])
#  -------------------------------------------------------------------

# Plot Optimization Results
#  -------------------------------------------------------------------
fig, axs = plt.subplots(3, 4, sharex=True)
fig.set_size_inches(10, 10, forward=True)
t_Nx = np.linspace(0, T, N)
t_Nu = np.linspace(0, T, N-1)
t_idx_x = t_Nx[0:Nidx]
t_idx_u = t_Nx[0:Nidx-1]
ctrl_g_idx = dyn.g_u.map(Nidx-1)
ctrl_g_val = ctrl_g_idx(U_plot, del_plot)
#  -------------------------------------------------------------------
# plot position
for i in range(dyn.Nx):
    axs[0, i].plot(t_Nx, X_nom_val[i, 0:N].T, color='red',
                   linestyle='--', label='nom')
    axs[0, i].plot(t_Nx, X_nom_val_opt[i, 0:N].T, color='blue',
                   linestyle='--', label='plan')
    axs[0, i].plot(t_idx_x, X_plot[i, :], color='orange', label='mpc')
    handles, labels = axs[0, i].get_legend_handles_labels()
    axs[0, i].legend(handles, labels)
    axs[0, i].set_xlabel('time [s]')
    axs[0, i].set_ylabel('x%d' % i)
    axs[0, i].grid()
#  -------------------------------------------------------------------
# plot computation time
axs[1, 0].plot(t_idx_u, comp_time, color='b')
handles, labels = axs[1, 0].get_legend_handles_labels()
axs[1, 0].legend(handles, labels)
axs[1, 0].set_xlabel('time [s]')
axs[1, 0].set_ylabel('comp time [s]')
axs[1, 0].grid()
#  -------------------------------------------------------------------
# plot computation cost
axs[1, 1].plot(t_idx_u, cost_plot, color='b', label='cost')
handles, labels = axs[1, 1].get_legend_handles_labels()
axs[1, 1].legend(handles, labels)
axs[1, 1].set_xlabel('time [s]')
axs[1, 1].set_ylabel('cost')
axs[1, 1].grid()
#  -------------------------------------------------------------------
# plot extra variables
for i in range(dyn.Nz):
    axs[1, 2].plot(t_idx_u, del_plot[i, :].T, label='s%d' % i)
handles, labels = axs[1, 2].get_legend_handles_labels()
axs[1, 2].legend(handles, labels)
axs[1, 2].set_xlabel('time [s]')
axs[1, 2].set_ylabel('extra vars')
axs[1, 2].grid()
#  -------------------------------------------------------------------
# plot constraints
for i in range(dyn.Ng_u):
    axs[1, 3].plot(t_idx_u, ctrl_g_val[i, :].T, label='g%d' % i)
handles, labels = axs[1, 3].get_legend_handles_labels()
axs[1, 3].legend(handles, labels)
axs[1, 3].set_xlabel('time [s]')
axs[1, 3].set_ylabel('constraints')
axs[1, 3].grid()
#  -------------------------------------------------------------------
# plot actions
for i in range(dyn.Nu):
    axs[2, i].plot(t_Nu, U_nom_val_opt[i, 0:N-1].T, color='blue',
                   linestyle='--', label='plan')
    axs[2, i].plot(t_idx_u, U_plot[i, :], color='orange', label='mpc')
    handles, labels = axs[2, i].get_legend_handles_labels()
    axs[2, i].legend(handles, labels)
    axs[2, i].set_xlabel('time [s]')
    axs[2, i].set_ylabel('u%d' % i)
    axs[2, i].grid()
#  -------------------------------------------------------------------

#  -------------------------------------------------------------------
plt.show()
#  -------------------------------------------------------------------
