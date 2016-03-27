def uniqueList(alist):
    """Fast order-preserving uniquing of a list.

    From http://code.activestate.com/recipes/52560/

    @param alist: a C{list}.
    """
    seen = {}
    return [seen.setdefault(e, e) for e in alist if e not in seen]
