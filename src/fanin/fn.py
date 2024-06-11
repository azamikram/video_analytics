import statistics as stat

_get_list_except = lambda l, e: [x for i, x in enumerate(l) if i != e]

def _get_summary_except(data, i):
    d = _get_list_except(data, i)
    if len(d) == 0: d = data

    return {'extract_min': float(min(d)),
            'extract_mean': float(stat.mean(d)),
            'extract_max': float(max(d)),
            'extract_std': float(stat.stdev(d))}

def handler(events, _):
    no_events = len(events)
    base_rsp = {'src': events[0]['src'],
                'detect_prob': events[0]['detect_prob']}

    e_sizes = [None] * no_events
    e_runtimes = [None] * no_events
    for i, e in enumerate(events):
        e_sizes[i] = e['input_sizes']['extract']
        e_runtimes[i] = e['runtimes']['extract']

    response = [None] * no_events
    for i, e in enumerate(events):
        response[i] = {**base_rsp, **e,
                       'runtimes': {**e['runtimes'], **_get_summary_except(e_runtimes, i)},
                       'input_sizes': {**e['input_sizes'], **_get_summary_except(e_sizes, i)}
                       }

    return {'detail': {'indeces': response}}
