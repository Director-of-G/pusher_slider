# ignore warnings
import warnings
warnings.filterwarnings('ignore')

import argparse

from time import time
import numpy as np

from FreeFinalTime.parameters import *
from FreeFinalTime.discretization import FirstOrderHold
from FreeFinalTime.scproblem import SCProblemDirectEvalPar
from utils import format_line, save_arrays

# from Models.dynamic_pushing_2d import Model
# from Models.dynamic_pushing_2d_plot import plot

from Models.dynamic_pushing_3d import Model
from Models.dynamic_pushing_3d_plot import plot


"""
Python implementation of the Successive Convexification algorithm.

Rocket trajectory model based on the
'Successive Convexification for 6-DoF Mars Rocket Powered Landing with Free-Final-Time' paper
by Michael Szmuk and Behçet Açıkmeşe.

Implementation by Sven Niederberger (s-niederberger@outlook.com)
"""


# ARGUMENTS-------------------------------------------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--save', action='store_true', default=False, help='Save optimal trajectory or not.')
parser.add_argument('--plot', action='store_true', default=False, help='Plot optimal trajectory or not.')
args = parser.parse_args()

m = Model()
m.nondimensionalize()

"""
# state and input
X = np.empty(shape=[m.n_x, K])
U = np.empty(shape=[m.n_u, K])

# INITIALIZATION--------------------------------------------------------------------------------------------------------
sigma = m.t_f_guess
X, U = m.initialize_trajectory(X, U)

# START SUCCESSIVE CONVEXIFICATION--------------------------------------------------------------------------------------
all_X = [m.x_redim(X.copy())]
all_U = [m.u_redim(U.copy())]
all_sigma = [sigma]
all_J = []
all_L = []

integrator = FirstOrderHold(m, K)
problem = SCProblemDirectEvalPar(m, K)

# INITIAL NON-LINEAR COST
X_nl_init = integrator.integrate_nonlinear_piecewise(X, U, sigma)
nonlinear_cost_dynamics = np.linalg.norm(X - X_nl_init, 1)
nonlinear_cost_constraints = m.get_nonlinear_cost(X=X, U=U)
nonlinear_cost = nonlinear_cost_dynamics + nonlinear_cost_constraints
all_J.append([nonlinear_cost_dynamics, nonlinear_cost_constraints, nonlinear_cost])

last_nonlinear_cost = None
converged = False
for it in range(iterations):
    t0_it = time()
    print('-' * 50)
    print('-' * 18 + f' Iteration {str(it + 1).zfill(2)} ' + '-' * 18)
    print('-' * 50)

    t0_tm = time()
    # discretize the continuous system and return a LTV
    A_bar, B_bar, C_bar, S_bar, z_bar = integrator.calculate_discretization(X, U, sigma)
    print(format_line('Time for transition matrices', time() - t0_tm, 's'))

    t0_lc = time()
    D_eq_bar, E_eq_bar, r_eq_bar, D_ineq_bar, E_ineq_bar, r_ineq_bar = m.calculate_constraint_linearization(X, U)
    print(format_line('Time for linearized constraints', time() - t0_lc, 's'))

    problem.set_parameters(A_bar=A_bar, B_bar=B_bar, C_bar=C_bar, S_bar=S_bar, z_bar=z_bar,
                           D_eq_bar=D_eq_bar, E_eq_bar=E_eq_bar, r_eq_bar=r_eq_bar,
                           D_ineq_bar=D_ineq_bar, E_ineq_bar=E_ineq_bar, r_ineq_bar=r_ineq_bar,
                           X_last=X, U_last=U, sigma_last=sigma,
                           weight_nu=w_nu, weight_sigma=w_sigma, tr_radius=tr_radius)

    while True:
        error = problem.solve(verbose=verbose_solver, solver=solver, max_iters=200)
        print(format_line('Solver Error', error))

        # get solution
        new_X = problem.get_variable('X')
        new_U = problem.get_variable('U')
        new_sigma = problem.get_variable('sigma')

        # rollout with the nonlinear dynamics
        X_nl = integrator.integrate_nonlinear_piecewise(new_X, new_U, new_sigma)

        linear_cost_dynamics = np.linalg.norm(problem.get_variable('nu'), 1)
        nonlinear_cost_dynamics = np.linalg.norm(new_X - X_nl, 1)

        linear_cost_constraints = m.get_linear_cost()
        nonlinear_cost_constraints = m.get_nonlinear_cost(X=new_X, U=new_U)

        linear_cost = linear_cost_dynamics + linear_cost_constraints  # J
        nonlinear_cost = nonlinear_cost_dynamics + nonlinear_cost_constraints  # L

        if last_nonlinear_cost is None:
            last_nonlinear_cost = nonlinear_cost
            X = new_X
            U = new_U
            sigma = new_sigma
            break

        actual_change = last_nonlinear_cost - nonlinear_cost  # delta_J
        predicted_change = last_nonlinear_cost - linear_cost  # delta_L

        print('')
        print(format_line('Virtual Control Cost', linear_cost_dynamics))
        print(format_line('Constraint Cost', linear_cost_constraints))
        print('')
        print(format_line('Actual change', actual_change))
        print(format_line('Predicted change', predicted_change))
        print('')
        print(format_line('Final time', sigma))
        print('')

        if abs(predicted_change) < 9e-5:
            converged = True
            X = new_X
            U = new_U
            break
        else:
            rho = actual_change / predicted_change
            if rho < rho_0:
                # reject solution
                tr_radius /= alpha
                print(f'Trust region too large. Solving again with radius={tr_radius}')
            else:
                # accept solution
                X = new_X
                U = new_U
                sigma = new_sigma

                print('Solution accepted.')

                if rho < rho_1:
                    print('Decreasing radius.')
                    tr_radius /= alpha
                elif rho >= rho_2:
                    print('Increasing radius.')
                    tr_radius *= beta

                last_nonlinear_cost = nonlinear_cost
                break

        problem.set_parameters(tr_radius=tr_radius)

        print('-' * 50)

    print('')
    print(format_line('Time for iteration', time() - t0_it, 's'))
    print('')

    all_X.append(m.x_redim(X.copy()))
    all_U.append(m.u_redim(U.copy()))
    all_sigma.append(sigma)
    all_J.append([nonlinear_cost_dynamics, nonlinear_cost_constraints, nonlinear_cost])
    all_L.append([linear_cost_dynamics, linear_cost_constraints, linear_cost])

    if converged:
        print(f'Converged after {it + 1} iterations.')
        break

all_X = np.stack(all_X)
all_U = np.stack(all_U)
all_sigma = np.array(all_sigma)
all_J = np.stack(all_J)
all_L = np.stack(all_L)
if not converged:
    print('Maximum number of iterations reached without convergence.')

# save trajectory to file for visualization
if args.save:
    save_arrays('output/trajectory/', {'X': all_X, 'U': all_U, 'sigma': all_sigma, 'J': all_J, 'L': all_L})

# plot trajectory
if args.plot:
    plot(m, all_X, all_U, all_sigma, all_J, all_L)
    pass
"""

# plot trajectory (from file)
folder_no = 40
_, _, _ = m.get_equations()
all_X = np.load('./output/trajectory/0{0}/X.npy'.format(folder_no))
all_U = np.load('./output/trajectory/0{0}/U.npy'.format(folder_no))
all_sigma = np.load('./output/trajectory/0{0}/sigma.npy'.format(folder_no))
all_J = np.load('./output/trajectory/0{0}/J.npy'.format(folder_no))
all_L = np.load('./output/trajectory/0{0}/L.npy'.format(folder_no))
plot(m, all_X, all_U, all_sigma, all_J, all_L)
