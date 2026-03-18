from neuron import h
import numpy as np


# Helper: local cells by pop
def _get_local_cells(sim, pop_name):
    return [c for c in sim.net.cells if c.tags['pop'] == pop_name]


class ConnFader:

    def __init__(self):
        self.conn_groups = {}
        self.sim = None
        self.T = 10
        self.dt = 0.1
        self.modulators = {}
    
    def add_conn_group(self, group_name, conns_pos, conns_neg, pts):
        """Add a group of connections to fade in/out together.

        conns_pos and conns_neg should be lists of conns, where the
        weight of conns_pos will be faded from 0 to their original value,
        and the weight of conns_neg will be faded from their original value
        to 0.
        pts is a list of time points at which to update the weights.
        """
        self.conn_groups[group_name] = {
            'conns_pos': conns_pos,
            'conns_neg': conns_neg,
            'pts': pts
        }
    
    def _generate_mod_signal(self, group_name):
        tvec = np.arange(0, self.T, self.dt)
        pts = self.conn_groups[group_name]['pts']
        pts = np.array(pts)
        zvec = np.interp(tvec, pts[:, 0], pts[:, 1])
        return tvec, zvec
    
    def _create_modulator(self, group_name, inv: bool):
        # Create modulator object
        cell = self.sim.net.cells[0]   # store in the 1st cell on this rank
        soma = cell['soma']['hObj']
        hmod = h.Modulator(soma(0.5))

        # Generate modulation signal
        tvec, zvec = self._generate_mod_signal(group_name)
        if inv:
            zvec = np.maximum(1 - zvec, 0)
        h_tvec = h.Vector(tvec)
        h_zvec = h.Vector(zvec)

        # Play the signal to the modulator object
        h_zvec.play(hmod._ref_z, h_tvec)

        mod_name = group_name + ('_neg' if inv else '_pos')
        self.modulators[mod_name] = {
            'group_name': group_name, 'inv': inv,
            'tvec': tvec, 'zvec': zvec,
            'hobj': hmod, 'h_tvec': h_tvec, 'h_zvec': h_zvec
        }




        # Record modulator signal
        #h_tvec, h_zvec = h.Vector(), h.Vector()
        #h_tvec.record(h._ref_t)
        #h_zvec.record(hmod._ref_z)





