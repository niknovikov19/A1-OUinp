from netpyne.batchtools import comm, specs
from neuron import h

cfg = specs.SimConfig()
cfg.batch_par = None
cfg.update()

pc = h.ParallelContext()
rank = int(pc.id())

print(f'>>>>> BATCH_PAR: {cfg.batch_par}, rank={rank}')

pc.barrier()

comm.initialize()
if comm.is_host():
    comm.send({'done': 1, 'batch_par': cfg.batch_par})

pc.barrier()