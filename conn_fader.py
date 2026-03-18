

class ConnFader:

    def __init__(self):
        self.conn_groups = {}
    
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
    
    