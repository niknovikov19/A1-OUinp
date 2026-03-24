import matplotlib.pyplot as plt
from neuron import h
import numpy as np


class ConnFader:

    def __init__(self, sim=None, T=10, dt=0.1):
        self.sim = sim
        self.T = T
        self.dt = dt
        self.conn_groups = {}
        self.modulators = {}
        self.conn_mod_map = {}
    
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
        soma = cell.secs['soma']['hObj']
        hmod = h.SharedVar(soma(0.5))

        # Generate modulation signal
        tvec, zvec = self._generate_mod_signal(group_name)
        if inv:
            zvec = np.maximum(1 - zvec, 0)
        h_tvec = h.Vector(tvec)
        h_zvec = h.Vector(zvec)

        # Play the signal to the modulator object
        h_zvec.play(hmod._ref_z, h_tvec)

        # Collect modulator info
        mod_name = group_name + ('_neg' if inv else '_pos')
        self.modulators[mod_name] = {
            'group_name': group_name, 'inv': inv,
            'tvec': tvec, 'zvec': zvec,
            'hobj': hmod, 'h_tvec': h_tvec, 'h_zvec': h_zvec
        }

        if self.sim.rank == 0:
            print(f"Created modulator {mod_name} for group {group_name} (inv={inv})")

        # Append conn -> modulator mapping
        conn_group = self.conn_groups[group_name]
        conns = conn_group['conns_neg'] if inv else conn_group['conns_pos']
        for conn_name in conns:
            if conn_name in self.conn_mod_map:
                raise ValueError(f"Conn. {conn_name} already assigned to a modulator")
            self.conn_mod_map[conn_name] = mod_name
            if self.sim.rank == 0:
                print(f"  Assigned conn {conn_name} to modulator {mod_name}")

    def create_modulators(self):
        for group_name in self.conn_groups:
            self._create_modulator(group_name, inv=False)
            self._create_modulator(group_name, inv=True)
    
    def connect_modulators(self):
        for cell in self.sim.net.cells:
            for conn in cell.conns:
                conn_name = conn.get('label')
                if conn_name in self.conn_mod_map:
                    mod_name = self.conn_mod_map[conn_name]
                    mod = self.modulators[mod_name]
                    hmod = mod['hobj']

                    syn = conn['hObj'].syn()
                    h.setpointer(hmod._ref_z_shared, 'pmod', syn)
                    syn.use_pmod = 1
                    syn.pmod0 = mod['zvec'][0]
                    
                    if 'syn' not in mod:
                        mod['syn'] = syn
                        if self.sim.rank == 0:
                            print(f"Connected modulator {mod_name} to synapse of conn {conn_name}")
    
    def setup_recording(self, rec_dt=None):
        """
        Record each modulator's z_shared.
        This has the same timecourse as syn.pmod for all synapses wired to it.
        """
        rec_dt = self.dt if rec_dt is None else rec_dt

        for mod_name, mod in self.modulators.items():
            hmod = mod['hobj']
            syn = mod['syn']

            mod['rec_t'] = h.Vector()
            mod['rec_z'] = h.Vector()

            # Point-process-first form is safer with local dt / threads
            #mod['rec_z'].record(hmod, hmod._ref_z_shared, rec_dt)
            mod['rec_z'].record(syn, syn._ref_g, rec_dt)
            mod['rec_t'].record(h._ref_t, rec_dt)

    def _get_local_recs(self):
        recs = {}
        for mod_name, mod in self.modulators.items():
            if 'rec_z' not in mod:
                continue
            recs[mod_name] = {
                't': np.array(mod['rec_t']),
                'z': np.array(mod['rec_z']),
            }
        return recs

    def gather_recs(self):
        """
        Gather all recorded traces from all MPI ranks.
        Returns the same list on every rank; element i came from rank i.
        """
        recs = self._get_local_recs()
        gathered = self.sim.pc.py_allgather(recs)
        self.gathered_recordings = gathered
        return gathered

    def plot_recs(self, gathered=None):
        """
        Plot on rank 0 only.
        """
        #if gathered is None:
        #    gathered = self.gathered_recordings
        #if gathered is None:
        #    raise RuntimeError("No gathered recordings found. Call gather_recordings() first.")

        if self.sim.rank != 0:
            return None

        plt.figure(figsize=(7, 4))
        #for _, rank_data in enumerate(gathered):
        #    for mod_name, rec in rank_data.items():
        #        plt.plot(rec['t'], rec['z'], label=f'{mod_name}')
        for mod_name, rec in self._get_local_recs().items():
            plt.plot(rec['t'], rec['z'], label=f'{mod_name}')

        plt.xlabel('Time (ms)')
        plt.ylabel('pmod')
        plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
        plt.tight_layout()
        plt.show()
