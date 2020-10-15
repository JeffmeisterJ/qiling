import gdb, os

try:
    from tqdm import tqdm
except ImportError:
    pass


def snapshot_cmd(cmd):
    return gdb.execute(f'monitor snapshot;{cmd}', to_string=True)


def get_snapshots_info():
    ret_info = snapshot_cmd('info')
    ret_snaps = [x.split(':') for x in ret_info.splitlines() if x]
    return {x: int(v, 16) for x, v in ret_snaps}


class SnapshotPrefixCommand(gdb.Command):
    """Command for controlling Qiling snapshots from a GDB client"""

    def __init__(self):
        super(SnapshotPrefixCommand, self).__init__("snapshot",
                                                    gdb.COMMAND_SUPPORT,
                                                    gdb.COMPLETE_NONE, True)
        SnapshotPrefixCommand.SnapshotSaveCommand()
        SnapshotPrefixCommand.SnapshotLoadCommand()
        SnapshotPrefixCommand.SnapshotInfoCommand()
        SnapshotPrefixCommand.SnapshotDeleteCommand()
        SnapshotPrefixCommand.SnapshotCreateCommand()
        SnapshotPrefixCommand.SnapshotRestoreCommand()

    class SnapshotCreateCommand(gdb.Command):
        """Create a snapshot from the current state"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot create", gdb.COMMAND_SUPPORT)

        def invoke(self, args, from_tty):
            argv = gdb.string_to_argv(args)
            name = None if not len(argv) else argv[0]

            cmd = f'create;name:{name}' if name else 'create'

            ret_name = snapshot_cmd(cmd)
            if (name and not ret_name == name) or 'SNAPSHOT ERR' in ret_name:
                raise gdb.GdbError(f'Snapshot creation failed! {ret_name}')
            else:
                gdb.write(f'Created snapshot {ret_name}\n')
                gdb.flush()

    class SnapshotRestoreCommand(gdb.Command):
        """Restore the current state to one of the available snapshots"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot restore", gdb.COMMAND_SUPPORT)

        def invoke(self, args, from_tty):
            argv = gdb.string_to_argv(args)
            if len(argv) != 1:
                raise gdb.GdbError(f'Usage: snapshot restore $snapshot_name')
            name = argv[0]
            if name not in get_snapshots_info():
                raise gdb.GdbError(f'Snapshot {name} not found!')

            cmd = f'restore;name:{name}'

            ret_name = snapshot_cmd(cmd)
            if (ret_name != name) or 'SNAPSHOT ERR' in ret_name:
                raise gdb.GdbError(f'Restoring snapshot failed! {ret_name}')
            else:
                gdb.write(f'Restored snapshot {ret_name}\n')
                gdb.flush()

    class SnapshotSaveCommand(gdb.Command):
        """Save a snapshot to a file"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot save", gdb.COMMAND_SUPPORT)

        def invoke(self, args, from_tty):
            argv = gdb.string_to_argv(args)
            if not len(argv) or len(argv) > 2:
                raise gdb.GdbError(f'Usage: snapshot save snapshot_name [file path]')
            name = argv[0]
            f_out = f'./{name}.qsp' if len(argv) == 1 else argv[2]
            if name not in get_snapshots_info():
                raise gdb.GdbError(f'Snapshot {name} not found!')
            if not os.path.exists(os.path.dirname(f_out)):
                raise gdb.GdbError(f'Directory {os.path.dirname(f_out)} does not exist!')
            if os.path.isdir(f_out):
                os.path.join(f_out, f'{name}.qsp')

            cmd = f'save;name:{name}'

            snap_data = snapshot_cmd(cmd)
            if 'SNAPSHOT ERR' in snap_data:
                raise gdb.GdbError(f'Saving snapshot failed!')
            else:
                with open(f_out, 'wb') as fh_out:
                    fh_out.write(bytes.fromhex(snap_data))
                gdb.write(f'Saved snapshot {name} to {f_out}\n')
                gdb.flush()

    class SnapshotLoadCommand(gdb.Command):
        """Load a snapshot from a file"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot load", gdb.COMMAND_SUPPORT)

        def invoke(self, args, from_tty):
            argv = gdb.string_to_argv(args)
            if not len(argv) or len(argv) > 2:
                raise gdb.GdbError(f'Usage: snapshot load file_path [name]')
            f_in = argv[0]
            if not os.path.exists(f_in):
                raise gdb.GdbError(f'Snapshot file {f_in} doesn\'t exist!')
            with open(f_in, 'rb') as fh_in:
                snap_data = fh_in.read()

            len_recv = int(snapshot_cmd(f'load;data:{snap_data[:1024].hex()};state:start'))
            if len_recv != len(snap_data[:1024]):
                raise gdb.GdbError(f'Error sending snapshot data (State: start, len_recv: {len_recv})!')

            rng = range(1024, len(snap_data), 1024)
            if 'tqdm' in globals():
                rng = tqdm(rng, unit_scale=1024, unit='B')

            for i in rng:
                len_recv = int(snapshot_cmd(f'load;data:{snap_data[i:i + 1024].hex()};state:cont'))
                if len_recv != len(snap_data[i:i + 1024]):
                    raise gdb.GdbError(f'Error sending snapshot data!')

            cmd = 'load;state:done'
            if len(argv) == 2:
                cmd += f';name:{argv[1]}'

            ret_name = snapshot_cmd(cmd)
            if 'SNAPSHOT ERR' in ret_name:
                raise gdb.GdbError(f'Saving snapshot failed!')
            else:
                gdb.write(f'Loaded snapshot {ret_name} from {f_in}\n')
                gdb.flush()

    class SnapshotInfoCommand(gdb.Command):
        """Get info about all the currently available snapshots"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot info", gdb.COMMAND_SUPPORT)

        def invoke(self, args, from_tty):
            ret_snaps = get_snapshots_info()
            gdb.write('\nOffset (PC): Name\n')
            gdb.write('-----------------\n')
            for name in ret_snaps:
                gdb.write(f'{hex(ret_snaps[name])}: {name}\n')
            gdb.write('\n')
            gdb.flush()

    class SnapshotDeleteCommand(gdb.Command):
        """Delete one of the currently available snapshots"""

        def __init__(self):
            gdb.Command.__init__(self, "snapshot delete", gdb.COMMAND_SUPPORT)


SnapshotPrefixCommand()
