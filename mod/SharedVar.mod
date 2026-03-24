NEURON {
    POINT_PROCESS SharedVar
    RANGE z, z_shared
}

ASSIGNED {
    z
    z_shared
}

BREAKPOINT {
    z_shared = z
}