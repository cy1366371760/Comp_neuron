"""
--- Computational Neurodynamics (COMP70100) ---

Part of the solution to Questions 1 and 2 in Exercise 2. This class can
simulate a network Izhikevich neurons with arbitrary parameters,
connectivities, and conduction delays. See docstrings of the methods and the
class itself for more information. Read through the comments in the code to
understand what it does.

Thanks to Paul Vanhaesebrouck for bug-hunting.

(C) Pedro Mediano, Murray Shanahan et al, 2016-2023
"""

import numpy as np
import random
import matplotlib.pyplot as plt

#--------------------------------- Start of IzNetwork class, referred from Exercise 2 ------------------------------------
class IzNetwork(object):
  """
  This class is used to simulate a network of Izhikevich neurons. The state of
  the neurons is automatically initialised, and parameters and connectivity
  matrices can be set with the appropriate setter methods. All class members are
  hidden (i.e. underscored) except for the state of the neurons (v,u).
  
  For both the delay and weight connectivity matrices, A[i,j] refers to the
  connection from neuron i to j. This was done this way (against standard
  convention) because the algorithm is easier to vectorise this way.
  
  Vectorisation with inhomogeneous time-delays is accomplished via a cylindrical
  accumulator array X, that is updated at every time step. More details in the
  inline comments.
  
  References:

  Izhikevich, E. M. (2003). Simple model of spiking neurons. IEEE Transactions
  on Neural Networks, 14(6), 1569-72. http://doi.org/10.1109/TNN.2003.820440

  Brette, R., & Goodman, D. F. M. (2011). Vectorized algorithms for spiking
  neural network simulation. Neural Computation, 23(6), 1503-35.
  http://doi.org/10.1162/NECO_a_00123

  """

  def __init__(self, N, Dmax):
    """
    Initialise network with given number of neurons and maximum transmission
    delay.

    Inputs:
    N     -- Number of neurons in the network.

    Dmax  -- Maximum delay in all the synapses in the network, in ms. Any
             longer delay will result in failing to deliver spikes.
    """
    self._Dmax   = Dmax + 1
    self._N      = N
    self._X      = np.zeros((Dmax + 1, N))
    self._I      = np.zeros(N)
    self._cursor = 0
    self._lastFired = np.array([False]*N)
    self._dt     = 0.1
    self.v       = -65.0*np.ones(N)
    self.u       = -1.0*np.ones(N)


  def setDelays(self, D):
    """
    Set synaptic delays.
    
    Inputs:
    D  -- np.array or np.matrix. The delay matrix must contain nonnegative
          integers, and must be of size N-by-N, where N is the number of
          neurons supplied in the constructor.
    """
    if D.shape != (self._N, self._N):
      raise Exception('Delay matrix must be N-by-N.')

    if not np.issubdtype(D.dtype, np.integer):
      raise Exception('Delays must be integer numbers.')

    if (D < 0.5).any():
      raise Exception('Delays must be strictly positive.')

    self._D = D


  def setWeights(self, W):
    """
    Set synaptic weights.

    Inputs:
    W  -- np.array or np.matrix. The weight matrix must be of size N-by-N,
          where N is the number of neurons supplied in the constructor.
    """
    if W.shape != (self._N, self._N):
      raise Exception('Weight matrix must be N-by-N.')
    self._W = np.array(W)


  def setCurrent(self, I):
    """
    Set the external current input to the network for this timestep. This
    only affects the next call to update().

    Inputs:
    I  -- np.array. Must be of length N, where N is the number of neurons
          supplied in the constructor.
    """
    if len(I) != self._N:
      raise Exception('Current vector must be of size N.')
    self._I = I


  def setParameters(self, a, b, c, d):
    """
    Set parameters for the neurons. Names are the the same as in Izhikevich's
    original paper, see references above. All inputs must be np.arrays of size
    N, where N is the number of neurons supplied in the constructor.
    """
    if (len(a), len(b), len(c), len(d)) != (self._N, self._N, self._N, self._N):
      raise Exception('Parameter vectors must be of size N.')

    self._a = a
    self._b = b
    self._c = c
    self._d = d


  def getState(self):
    """
    Get current state of the network. Outputs a tuple with two np.arrays,
    corresponding to the V and the U of the neurons in the network in this
    timestep.
    """
    return (self.v, self.u)


  def update(self):
    """
    Simulate one millisecond of network activity. The internal dynamics
    of each neuron are simulated using the Euler method with step size
    self._dt, and spikes are delivered every millisecond.

    Returns the indices of the neurons that fired this millisecond.
    """

    # Reset neurons that fired last timestep
    self.v[self._lastFired]  = self._c[self._lastFired]
    self.u[self._lastFired] += self._d[self._lastFired]

    # Input current is the sum of external and internal contributions
    I = self._I + self._X[self._cursor%self._Dmax,:]

    # Update v and u using the Izhikevich model and Euler method. To avoid
    # overflows with large input currents, keep updating only neurons that
    # haven't fired this millisecond.
    fired = np.array([False]*self._N)
    for _ in range(int(1/self._dt)):
        notFired = np.logical_not(fired)
        v = self.v[notFired]
        u = self.u[notFired]
        self.v[notFired] += self._dt*(0.04*v*v + 5*v + 140 - u + I[notFired])
        self.u[notFired] += self._dt*(self._a[notFired]*(self._b[notFired]*v - u))
        fired = np.logical_or(fired, self.v > 30)

    # Find which neurons fired this timestep. Their membrane potential is
    # fixed at 30 for visualisation purposes, and will be reset according to
    # the Izhikevich equation in the next iteration
    fired_idx = np.where(fired)[0]
    self._lastFired = fired
    self.v[fired]   = 30*np.ones(len(fired_idx))

    # Clear current for next timestep
    self._I = np.zeros(self._N)

    # Here's where the magic happens. For each firing "source" neuron i and
    # each "target" neuron j, we add a contribution W[i,j] to the accumulator
    # D[i,j] timesteps into the future. That way, as the cursor moves X
    # contains all the input coming from time-delayed connections.
    for i in fired_idx:
      self._X[(self._cursor + self._D[i, :])%self._Dmax, range(self._N)] += self._W[i,:]

    # Increment the cursor for the cylindrical array and clear accumulator
    self._X[self._cursor%self._Dmax,:] = np.zeros(self._N)
    self._cursor += 1

    return fired_idx
#-------------------------------------------- End of IzNetwork class --------------------------------------------

class ModularNetwork(object):
  # md_num = module number, excit = number of excitatory in each Module, inhib = number of inhibitory each neuron
  def __init__(self, md_num, excit, inhib): 
    self.md_num = md_num
    # module list, contain excitatory described by range : [range(0,100), range(100,200), ..., range(700,800)]
    self.md_excit_lst = []
    idx = 0
    for i in range(0, md_num):
      self.md_excit_lst.append(range(idx, idx + excit))
      idx = idx + excit
    self.excit = range(0, idx) # range for all excitatory neurons
    self.inhib = range(idx, idx + inhib) # range for all inhibitory neurons
    idx = idx + inhib
    self.connection = np.zeros((idx, idx)) # connection matrix
    self.delay_coef = np.zeros((idx, idx), dtype=int) # delay matrix
    self.wt_coef = np.zeros((idx, idx)) # weight matrix

  # generate modular small world network, md_lst: list of module, md_each: number of neuron in each module, p: probability of rewiring
  def gen_modular_small_world(self, md_lst, md_each, p):
    all_node_lst = []
    # create random one-way connection
    for md in md_lst:
      node_lst = list(md)
      all_node_lst.extend(node_lst)
      for _ in range(md_each):
        i = random.choice(node_lst)
        j = random.choice(node_lst)
        while i == j or self.connection[i][j]:
          i = random.choice(node_lst)
          j = random.choice(node_lst)
        self.connection[i][j] = 1

    # rewiring with probability p
    for md in md_lst:
      other_md = list(set(all_node_lst) - set(md))
      for i in md:
        for j in md:
          if self.connection[i][j]:
            if random.uniform(0, 1) < p:
              self.connection[i][j] = 0
              k = random.choice(other_md)
              while self.connection[i][k]:
                k = random.choice(other_md)
              self.connection[i][k] = 1

  # generate random coefficient matrix for weight or delay
  def gen_coef(self, target_matrix, fr_range, to_range, min_val, max_val, need_int = False):
    for i in fr_range:
      for j in to_range:
        if need_int:
          target_matrix[i][j] = random.randint(min_val, max_val)
        else:
          target_matrix[i][j] = random.uniform(min_val, max_val)

  # add excitatory to excitatory connection, use modular small world network
  def add_ex2ex_connection(self, md_each, p, wt_min, wt_max, scaling, delay_min, delay_max):
    self.gen_modular_small_world(self.md_excit_lst, md_each, p)
    self.gen_coef(self.wt_coef, self.excit, self.excit, wt_min * scaling, wt_max * scaling)
    self.gen_coef(self.delay_coef, self.excit, self.excit, delay_min, delay_max, need_int = True)

  # add excitatory to inhibitory connection, 4 excitatory neurons to 1 inhibitory neuron
  def add_ex2in_connection(self, wt_min, wt_max, scaling, delay_min, delay_max):

    # Create random excitatory-to-inhibitory connections
    remain_md_excit_lst = self.md_excit_lst.copy()
    for i in self.inhib:
      fr_md = random.choice(range(0, self.md_num))
      while len(remain_md_excit_lst[fr_md]) < 4:
        fr_md = random.choice(range(0, self.md_num))
      chosen = random.sample(remain_md_excit_lst[fr_md], 4)
      for j in chosen:
        self.connection[j][i] = 1
      remain_md_excit_lst[fr_md] = list(set(remain_md_excit_lst[fr_md]) - set(chosen))

    self.gen_coef(self.wt_coef, self.excit, self.inhib, wt_min * scaling, wt_max * scaling)
    self.gen_coef(self.delay_coef, self.excit, self.inhib, delay_min, delay_max, need_int = True)

  # add inhibitory to excitatory connection, each inhibitory neuron to all excitatory neurons
  def add_in2ex_connection(self, wt_min, wt_max, scaling, delay_min, delay_max):

    for i in self.inhib:
      for j in self.excit:
        self.connection[i][j] = 1
    self.gen_coef(self.wt_coef, self.inhib, self.excit, wt_min * scaling, wt_max * scaling)
    self.gen_coef(self.delay_coef, self.inhib, self.excit, delay_min, delay_max, need_int = True)

  # add inhibitory to inhibitory connection, each inhibitory neuron to all other inhibitory neurons
  def add_in2in_connection(self, wt_min, wt_max, scaling, delay_min, delay_max):

    for i in self.inhib:
      for j in self.inhib:
        if i != j:
          self.connection[i][j] = 1
    self.gen_coef(self.wt_coef, self.inhib, self.inhib, wt_min * scaling, wt_max * scaling)
    self.gen_coef(self.delay_coef, self.inhib, self.inhib, delay_min, delay_max, need_int = True)

  # plot connection matrix
  def plot_connection(self, p=0.1, show=False):
    # Create matrix for counting connections between modules
    n_modules = self.md_num + 1  # +1 for inhibitory module
    connection_matrix = np.zeros((n_modules, n_modules))
    
    # Count connections between excitatory modules
    for i in range(self.md_num):
        for j in range(self.md_num):
            count = 0
            for src in self.md_excit_lst[i]:
                for dst in self.md_excit_lst[j]:
                    if self.connection[src][dst] == 1:
                        count += 1
            connection_matrix[i][j] = count
    
    # Count connections to/from inhibitory module
    for i in range(self.md_num):
        # Excitatory to inhibitory
        count_to_inhib = 0
        for src in self.md_excit_lst[i]:
            for dst in self.inhib:
                if self.connection[src][dst] == 1:
                    count_to_inhib += 1
        connection_matrix[i][-1] = count_to_inhib
        
        # Inhibitory to excitatory
        count_from_inhib = 0
        for src in self.inhib:
            for dst in self.md_excit_lst[i]:
                if self.connection[src][dst] == 1:
                    count_from_inhib += 1
        connection_matrix[-1][i] = count_from_inhib
    
    # Count inhibitory to inhibitory connections
    inhib_count = 0
    for src in self.inhib:
        for dst in self.inhib:
            if self.connection[src][dst] == 1:
                inhib_count += 1
    connection_matrix[-1][-1] = inhib_count
    
    # Create figure with two subplots
    plt.figure(figsize=(10, 10))
    
    # Plot 1: Connection matrix as heatmap
    # plt.subplot(121)
    
    # Apply log transformation (adding small constant to avoid log(0))
    log_matrix = np.log1p(connection_matrix)
    
    # Create heatmap with visible grid
    im = plt.imshow(log_matrix, cmap='YlOrRd')
    # plt.grid(True, which='minor', color='black', linewidth=0.5)
    # plt.grid(True, which='major', color='black', linewidth=1)
    
    # Add colorbar with original values
    # cbar = plt.colorbar(im)
    # cbar.set_label('Connections', rotation=270, labelpad=15)
    
    # Add labels
    module_labels = [f'Excit_M{i+1}' for i in range(self.md_num)] + ['Inhib']
    plt.xticks(range(n_modules), module_labels, fontweight='bold', rotation=0)
    plt.yticks(range(n_modules), module_labels, fontweight='bold')
    
    # Move labels to left and top
    ax = plt.gca()
    ax.xaxis.set_label_position('top')
    ax.xaxis.set_ticks_position('top')
    
    # Add text annotations with original values
    for i in range(n_modules):
        for j in range(n_modules):
            plt.text(j, i, int(connection_matrix[i][j]), 
                    ha='center', va='center', 
                    color='black' if log_matrix[i][j] < log_matrix.max()/2 else 'white',
                    fontweight='bold', fontsize=8)
    
    plt.title('Connection Matrix (edges between modules), p = {}'.format(p), pad=30, fontweight='bold', fontsize=14)
    
    # Draw grid lines
    plt.grid(True, which='minor', color='black', linewidth=0.5)
    if show:
        plt.show()
    plt.savefig('connection_matrix_p={}.pdf'.format(p))

  # simulate network with Izhikevich model, draw raster plot and firing rate
  def simulate_network(self, duration=1000, p=0.1, show=False):
      # Izhikevich, a b c d are parameters for excitatory and inhibitory neurons
      # same as Exercise 2
      N = len(self.excit) + len(self.inhib)
      a = []
      b = []
      c = []
      d = []
      for i in range(len(self.excit)):
        r = random.uniform(0, 1)
        ex_a = 0.02
        ex_b = 0.2
        ex_c = -65 + 15*(r**2)
        ex_d = 8 - 6*(r**2)
        a.append(ex_a)
        b.append(ex_b)
        c.append(ex_c)
        d.append(ex_d)
      
      for i in range(len(self.inhib)):
        r = random.uniform(0, 1)
        in_a = 0.02 + 0.08*r
        in_b = 0.25 - 0.05*r
        in_c = -65
        in_d = 2
        a.append(in_a)
        b.append(in_b)
        c.append(in_c)
        d.append(in_d)

      a = np.array(a)
      b = np.array(b)
      c = np.array(c)
      d = np.array(d)

      iz_network = IzNetwork(N, 20)
      iz_network.setParameters(a, b, c, d)
      iz_network.setWeights(self.wt_coef * self.connection)
      iz_network.setDelays(self.delay_coef)

      V = np.zeros((duration, len(self.excit)))
      # simulate duration ms
      for t in range(duration):
        I = np.random.poisson(lam = 0.01, size = N)
        I[I > 0] = 1
        I.dtype = 'int'
        I = I * 15
        iz_network.setCurrent(I)
        iz_network.update()
        V[t,:] = iz_network.getState()[0][0:len(self.excit)]
        # print(t, np.count_nonzero(V[t] > 29))
      t, n = np.where(V > 29)
      plt.figure(figsize=(20, 5))
      plt.scatter(t, n)
      plt.title('Raster Plot of Neuron Firing, p = {}'.format(p))
      plt.xlabel('Time (ms) + 0s', loc = 'center')
      plt.ylabel('Neuron number')
      plt.ylim(len(network.excit), 0)
      plt.xlim(0, 1001)
      plt.xticks(range(0, 1001, 100))
      if show:
        plt.show()
      plt.savefig('raster_plot_p={}.pdf'.format(p))

      x = [20 * i for i in range(0, 50)]
      ys = []
      for md in self.md_excit_lst:
        y = [0] * 50
        for i in range(0, 50):
          mid = i * 20
          l = max(mid - 25, 0)
          r = min(mid + 25, 1000)
          y[i] = np.count_nonzero(V[l:r, md] > 29) / (r - l)
        ys.append(y)
      plt.figure(figsize=(20, 5))
      for y in ys:
        plt.plot(x, y)
      plt.title('Firing rate of each module, p = {}'.format(p))
      plt.xlabel('Time (ms) + 0s', loc = 'center')
      plt.ylabel('Mean Firing rate')
      plt.xlim(0, 1001)
      plt.xticks(range(0, 1001, 100))
      if show:
        plt.show()
      plt.savefig('firing_rate_p={}.pdf'.format(p))

if __name__ == '__main__':
  # different probability of rewiring
  p_test = [0, 0.1, 0.2, 0.3, 0.4, 0.5]
  for p in p_test:
    # parameters from slide
    network = ModularNetwork(8, 100, 200)
    network.add_ex2ex_connection(md_each=1000, p=p, wt_min=1,
                                wt_max=1, scaling=17, delay_min=1, delay_max=20)
    network.add_ex2in_connection(wt_min=0, wt_max=1, scaling=50, delay_min=1, delay_max=1)
    network.add_in2ex_connection(wt_min=-1, wt_max=0, scaling=2, delay_min=1, delay_max=1)
    network.add_in2in_connection(wt_min=-1, wt_max=0, scaling=1, delay_min=1, delay_max=1)
    network.plot_connection(p=p)
    network.simulate_network(duration=1000, p=p)