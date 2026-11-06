"""Windows equivalents for upstream Unix locking and peak-memory reporting."""
import os
import time

if os.name != 'nt':
    import fcntl as file_lock
else:
    import msvcrt
    class file_lock:
        LOCK_EX, LOCK_NB, LOCK_UN = 2, 4, 8
        @staticmethod
        def flock(stream, flags):
            fd = stream.fileno()
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'\0')
            os.lseek(fd, 0, os.SEEK_SET)
            if flags & file_lock.LOCK_UN:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                return
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    return
                except OSError as exc:
                    if flags & file_lock.LOCK_NB:
                        raise BlockingIOError('Execution lease is already held') from exc
                    time.sleep(.02)


def peak_memory_bytes():
    if os.name != 'nt':
        import resource
        import sys
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == 'darwin' else peak*1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
            'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    data = Counters();data.cb = ctypes.sizeof(data)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not get_memory(get_process(), ctypes.byref(data), data.cb):
        raise ctypes.WinError()
    return data.PeakWorkingSetSize
