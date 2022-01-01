import multiprocessing


def get_type_list(types):
    type_classes = {
        "STRING": str,
        "INT": int,
        "FLOAT": float,
        "DICT": dict,
        "LIST": list,
        "BOOL": bool
    }

    return tuple([type_classes[i] for i in types.split("|")])


def count_in_process(func, args):
    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=func, args=(queue, args))
    process.start()
    process.join()
    return queue.get()
