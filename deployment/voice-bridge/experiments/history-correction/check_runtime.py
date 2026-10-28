"""Compare Compose environment, published ports and networks without secrets."""
import collections
import json
import sys


def _environment(items):
    if not isinstance(items, list):
        raise ValueError('Container or image environment has an unexpected format')
    result = {}
    for item in items:
        if not isinstance(item, str) or '=' not in item:
            raise ValueError('Container or image environment has an unexpected format')
        key, value = item.split('=', 1)
        if key in result:
            raise ValueError('Container or image has duplicate environment keys')
        result[key] = value
    return result


def check(compose, container, image):
    try:
        svc = compose['services']['voicepipeline']
        config = container['Config']
        host = container['HostConfig']
        image_config = image['Config']
        networks = container['NetworkSettings']['Networks']
    except (KeyError, TypeError):
        raise ValueError('Compose, container or image inspection is incomplete')
    if container.get('Image') != image.get('Id'):
        raise ValueError('The Compose image does not match the running image')
    expected_env = _environment(image_config.get('Env') or [])
    service_env = svc.get('environment') or {}
    if not isinstance(service_env, dict) or any(value is None for value in service_env.values()):
        raise ValueError('An unresolved Compose environment value prevents comparison')
    for key, value in service_env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('Compose environment has an unexpected format')
        expected_env[key] = value
    if expected_env != _environment(config.get('Env') or []):
        raise ValueError('Running environment differs from the resolved Compose and image environment')

    # Compare the main execution settings, taking defaults from the image.
    for compose_key, image_key, runtime_key in (
        ('entrypoint', 'Entrypoint', 'Entrypoint'),
        ('command', 'Cmd', 'Cmd'),
    ):
        expected = svc.get(compose_key)
        if expected is None:
            expected = image_config.get(image_key)
        actual = config.get(runtime_key)
        if (expected is not None and not isinstance(expected, list)) or (actual is not None and not isinstance(actual, list)):
            raise ValueError('Container command or entrypoint requires manual review')
        if expected != actual:
            raise ValueError('Running command or entrypoint differs from Compose and image')
    for compose_key, image_key, runtime_key in (
        ('user', 'User', 'User'), ('working_dir', 'WorkingDir', 'WorkingDir'),
    ):
        expected = svc.get(compose_key)
        if expected is None:
            expected = image_config.get(image_key) or ''
        if str(expected) != str(config.get(runtime_key) or ''):
            raise ValueError('Running user or working directory differs from Compose and image')
    for compose_key, runtime_key in (('tty', 'Tty'), ('stdin_open', 'OpenStdin')):
        if bool(svc.get(compose_key, False)) != bool(config.get(runtime_key, False)):
            raise ValueError('Running terminal configuration differs from Compose')
    for compose_key, runtime_key in (('privileged', 'Privileged'), ('read_only', 'ReadonlyRootfs')):
        if bool(svc.get(compose_key, False)) != bool(host.get(runtime_key, False)):
            raise ValueError('Running privilege or root filesystem mode differs from Compose')
    restart = svc.get('restart') or 'no'
    if not isinstance(restart, str):
        raise ValueError('Restart policy requires manual review')
    pieces = restart.split(':', 1)
    try:
        retry = int(pieces[1]) if len(pieces) == 2 else 0
    except ValueError:
        raise ValueError('Restart policy requires manual review')
    actual_restart = host.get('RestartPolicy') or {}
    if (pieces[0], retry) != (actual_restart.get('Name') or 'no', actual_restart.get('MaximumRetryCount') or 0):
        raise ValueError('Running restart policy differs from Compose')
    def capabilities(values):
        return sorted(str(v).upper().removeprefix('CAP_') for v in values or [])
    for compose_key, runtime_key in (('cap_add', 'CapAdd'), ('cap_drop', 'CapDrop')):
        if capabilities(svc.get(compose_key)) != capabilities(host.get(runtime_key)):
            raise ValueError('Running capabilities differ from Compose')
    if any(svc.get(key) for key in ('devices', 'device_cgroup_rules', 'security_opt', 'extra_hosts', 'dns', 'dns_search', 'dns_opt', 'deploy', 'mem_limit', 'cpus', 'cpuset', 'cpu_quota', 'cpu_period', 'shm_size')):
        raise ValueError('Devices, security, DNS or resource limits require manual review')
    if any(host.get(key) for key in ('Devices', 'DeviceCgroupRules', 'SecurityOpt', 'ExtraHosts', 'Dns', 'DnsSearch', 'DnsOptions', 'Memory', 'NanoCpus', 'CpusetCpus', 'CpuQuota', 'CpuPeriod')):
        raise ValueError('Running devices, security, DNS or resource limits require manual review')

    expected_ports = []
    for port in svc.get('ports') or []:
        if not isinstance(port, dict) or 'target' not in port or 'published' not in port:
            raise ValueError('Compose ports have an unsupported format')
        published = str(port['published'])
        if not published.isdigit() or int(published) == 0:
            raise ValueError('A dynamic or ranged published port cannot be verified automatically')
        expected_ports.append((str(port['target']), str(port.get('protocol', 'tcp')).lower(),
                               str(port.get('host_ip') or ''), published))
    actual_ports = []
    bindings = host.get('PortBindings') or {}
    if not isinstance(bindings, dict):
        raise ValueError('Running ports have an unsupported format')
    for target, entries in bindings.items():
        try:
            port, protocol = target.split('/', 1)
        except (ValueError, AttributeError):
            raise ValueError('Running ports have an unsupported format')
        for binding in entries or []:
            actual_ports.append((str(port), protocol.lower(), str(binding.get('HostIp') or ''),
                                 str(binding.get('HostPort') or '')))
    if collections.Counter(expected_ports) != collections.Counter(actual_ports):
        raise ValueError('Running published port bindings differ from Compose')

    desired_mode = svc.get('network_mode')
    if desired_mode:
        if desired_mode not in ('host', 'none', 'bridge'):
            raise ValueError('This network mode requires manual review')
        if host.get('NetworkMode') != desired_mode:
            raise ValueError('Running network mode differs from Compose')
    else:
        declared = svc.get('networks') or {'default': None}
        project_networks = compose.get('networks') or {}
        if not isinstance(declared, (dict, list)) or not isinstance(networks, dict):
            raise ValueError('Compose or runtime networks have an unsupported format')
        expected = set()
        for key in declared:
            definition = project_networks.get(key)
            if not isinstance(definition, dict) or not definition.get('name'):
                raise ValueError('A Compose network name cannot be resolved')
            expected.add(definition['name'])
        if expected != set(networks):
            raise ValueError('Running attached networks differ from Compose')
    return True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: check_runtime.py COMPOSE CONTAINER IMAGE')
    try:
        values = []
        for path in sys.argv[1:]:
            with open(path, encoding='utf-8') as stream:
                values.append(json.load(stream))
        compose, containers, images = values
        if not isinstance(containers, list) or len(containers) != 1 or not isinstance(images, list) or len(images) != 1:
            raise ValueError('Expected one running container and one image')
        check(compose, containers[0], images[0])
        print('Running environment matches the resolved Compose and image environment.')
        print('Running published ports and network configuration match Compose.')
        print('Common execution, restart, privilege and capability settings match.')
        print('Values were compared locally and were not printed.')
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit('Runtime check failed: ' + str(exc))
