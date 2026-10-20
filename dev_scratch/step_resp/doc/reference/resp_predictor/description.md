## Goal

We have a network of $N$ interconnected neural populations.
Each population recieves recurrent inputs from other populations and from itself. Also, it recieves an external input. 
The state of a population is characterized by its firing rate.

Let's denote the external input to $n$-th population as $h_n$, and its firing rate as $r_n$.
The state and inputs of the whole network can be expressed in a vectorized form:
$$
\bar{r} = (r_1, ..., r_N)^T \\
\bar{h} = (h_1, ..., h_N)^T
$$

We can simulate our network for a constant $\bar{h}$ and get $\bar{r}$ from the simulation result (assume the network has a steady state). 
Thus, **we can consider $\bar{h}$ as an input, $\bar{r}$ as an output, and the network as a "black box" that performs a mapping $\bar{h}\rightarrow\bar{r}$**. In general, we don't know the mapping explicitly, only via simulations.

If $N$ is small, we can define an $N$-dimensional grid and probe every $\bar{h}$ from this grid - simulate the network and find the corresponding $\bar{r}$. But as $N$ grows, it quickly becomes impossible. 

**It would be nice to get an impression about the $\bar{h}\rightarrow\bar{r}$ mapping by running a realistic number of simulations.**


## Motivation

Assume for a moment that we explicitly know the dynamical system for our network:
$$
\tau dr_n/dt = -r_n + f_n(\bar{r}, h_n), \\
n = 1, 2, ..., N
$$

Or, in vectorized form:
$$
\tau d\bar{r}/dt = -\bar{r} + F(\bar{r}, \bar{h}), \\
F = (f_1, ... , f_n)
$$

For a constant $\bar{h}=\bar{h}_0$, the system will converge to a steady state $\bar{r}_0$ (if it does exist), such that:
$$
\bar{r}_0 = F(\bar{r}_0, \bar{h}_0)
$$

Let's expand $F$ about $(\bar{r}_0, \bar{h}_0)$ up to the 1-st order:
$$ 
\bar{r}_0 + \Delta\bar{r} = F(\bar{r}_0 + \Delta\bar{r}, \bar{h}_0 + \Delta\bar{h}) \approx \\
\approx F(\bar{r}_0, \bar{h}_0) + J \Delta\bar{r} + Q \Delta\bar{h}
$$
where $J$ and $Q$ are two matrices, given by:
$$
J_{kn} = {\partial f_k} / {\partial r_n} |_{r_0, h_0} \\
Q_{nn} = {\partial f_n} / {\partial h_n} |_{r_0, h_0} \\
Q_{kn} = 0 \text{  for  } k \neq n
$$

Because $\bar{r}_0 = F(\bar{r}_0, \bar{h}_0)$, we get a linear system:
$$
\Delta\bar{r} = J \Delta\bar{r} + Q \Delta\bar{h}
$$

which can be solved for $\Delta\bar{r}$, given an arbitrary $\Delta\bar{h}$.
Thus, we have an **approximation for the input-output mapping** performed by the system: 
$$
\bar{h}_0 + \Delta\bar{h} \rightarrow \bar{r}_0 + \Delta\bar{r}
$$.


## Idea

