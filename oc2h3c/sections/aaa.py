"""AAA mapping: password-control defaults, local users, SSH users, HWTACACS
server group and ISP domain policy.

Every emitted value is read from the OC document (``system/aaa`` and the
``system/config`` domain name).  The reference transcript fixes several keyword
sets and mapping policies that the OC cannot express: the password-control
negatives, the local-user class / service-type list / default-role removal, the
HWTACACS key and user-name-format keywords, the primary/secondary role
selection policy, the terminal ``none`` fallback of command authorization and
the blocked preset ISP domain ``system``.  Each such decision is reported with
``ctx.ambiguous``.
"""

# The password-control feature is not modelled by the OC document; the native
# transcript disables the five password-control defaults.
PASSWORD_CONTROL_UNDO = (
    'undo password-control complexity user-name check',
    'undo password-control enable',
    'undo password-control login idle-time',
    'undo password-control length enable',
    'undo password-control composition enable',
)

LOCAL_USER_SERVICE_TYPES = ('https', 'ssh', 'terminal')
REMOVED_DEFAULT_ROLE = 'network-operator'
SSH_SERVICE_TYPE = 'all'
SSH_AUTHENTICATION_TYPE = 'password'
HWTACACS_ROLES = ('authentication', 'authorization', 'accounting')
DEFAULT_HWTACACS_PORT = '49'

AAA = ('system', 'aaa')
SERVER_GROUPS = AAA + ('server-groups', 'server-group')
USERS = AAA + ('authentication', 'users', 'user')
SSH_USERS = AAA + ('authentication', 'users')
METHOD_ATTRIBUTES = {
    'authentication': 'authentication-method',
    'authorization': 'authorization-method',
    'accounting': 'accounting-method',
}


def _num_key(text):
    text = str(text)
    return (0, int(text)) if text.isdigit() else (1, text)


def _ordered_items(ctx, *parts):
    return sorted(ctx.items(*parts), key=lambda item: _num_key(item[0]))


def _server_group_kind(ctx, name):
    """Return 'tacacs'/'radius' from the server entries, without marking use."""
    base = SERVER_GROUPS + (name, 'servers', 'server')
    kind = None
    for _server, node in ctx.items(*base):
        if 'tacacs' in node:
            kind = 'tacacs'
        elif 'radius' in node and kind is None:
            kind = 'radius'
    return kind


# --------------------------------------------------------------------- users
def _read_local_users(ctx):
    users = []
    for name, _node in _ordered_items(ctx, *USERS):
        base = USERS + (name,)
        ctx.val(*(base + ('username',)))
        username = ctx.val(*(base + ('config', 'username')), default=name) or name
        users.append({
            'key': name,
            'username': username,
            'password': ctx.val(*(base + ('config', 'password'))),
            'role': ctx.val(*(base + ('config', 'role'))),
        })
    return users


def _emit_local_users(ctx, group, users):
    for user in users:
        role = user['role']
        user_class = 'manage' if role in ('network-admin', 'network-operator') else 'network'
        base = USERS + (user['key'],)
        group.append('local-user %s class %s' % (user['username'], user_class))
        if user['password'] is None:
            ctx.unsupported(base + ('config', 'password'),
                            'local user has no password value; password line omitted')
        else:
            group.append('password simple %s' % user['password'])
        group.append('service-type %s' % ' '.join(LOCAL_USER_SERVICE_TYPES))
        if role:
            group.append('authorization-attribute user-role %s' % role)
        else:
            ctx.unsupported(base + ('config', 'role'),
                            'local user has no role value; authorization-attribute omitted')
        group.append('undo authorization-attribute user-role %s' % REMOVED_DEFAULT_ROLE)

    if users:
        ctx.ambiguous(USERS,
                      'the OC document has no local-user class, service-type or '
                      'default-role-removal field',
                      "roles network-admin/network-operator map to class manage and "
                      "all other roles to class network; the fixed service-type list "
                      "'%s' and the default '%s' role removal are reproduced from the "
                      "reference" % (' '.join(LOCAL_USER_SERVICE_TYPES),
                                     REMOVED_DEFAULT_ROLE))
        ctx.ambiguous(USERS + ('config', 'password'),
                      'the OC password leaf carries no hash/plaintext indicator',
                      "the reference stores local-user passwords as 'password simple'; "
                      "the OC value is emitted as clear text")
        ctx.ambiguous(USERS + ('config', 'role'),
                      'the reference removes the default network-operator role from '
                      'the local user by an explicit undo line',
                      "the fixed 'undo authorization-attribute user-role %s' line is "
                      'reproduced after the configured role' % REMOVED_DEFAULT_ROLE)


def _emit_ssh_users(ctx, group, users):
    for user in users:
        group.append('ssh user %s service-type %s authentication-type %s'
                     % (user['username'], SSH_SERVICE_TYPE, SSH_AUTHENTICATION_TYPE))
    if users:
        ctx.ambiguous(SSH_USERS,
                      'the OC ssh-server subtree only carries enable/filter settings; '
                      'the SSH service type and authentication type are not modelled',
                      'every local user is declared as an SSH user with the fixed '
                      "'service-type %s authentication-type %s' of the reference"
                      % (SSH_SERVICE_TYPE, SSH_AUTHENTICATION_TYPE))


# ----------------------------------------------------------------- HWTACACS
def _read_servers(ctx, group_name):
    base = SERVER_GROUPS + (group_name, 'servers', 'server')
    servers = []
    for server, _node in _ordered_items(ctx, *base):
        sbase = base + (server,)
        cfg_address = ctx.val(*(sbase + ('config', 'address')))
        leaf_address = ctx.val(*(sbase + ('address',)))
        servers.append({
            'path': sbase,
            'index': ctx.int_val(*(sbase + ('config', 'index'))),
            'priority': ctx.int_val(*(sbase + ('config', 'priority'))),
            'address': cfg_address or leaf_address or server,
            'port': ctx.val(*(sbase + ('config', 'tcp-port'))),
            'key': ctx.val(*(sbase + ('tacacs', 'config', 'secret-key'))),
            'source': ctx.val(*(sbase + ('tacacs', 'config', 'source-address'))),
            'vpn': ctx.val(*(sbase + ('network-instance', 'config', 'name'))),
        })
    servers.sort(key=lambda item: (item['index'] if item['index'] is not None else 1 << 30,
                                   -(item['priority'] or 0)))
    return servers


def _common_value(servers, field):
    values = {server[field] for server in servers if server[field] is not None}
    if len(values) == 1:
        return values.pop()
    return None


def _server_suffix(record, common_key, common_vpn):
    args = []
    port = record['port']
    if port and port != DEFAULT_HWTACACS_PORT:
        args.append(port)
    if common_key is None and record['key'] is not None:
        args.append('key simple %s' % record['key'])
    if common_vpn is None and record['vpn']:
        args.append('vpn-instance %s' % record['vpn'])
    return (' ' + ' '.join(args)) if args else ''


def _emit_hwtacacs(ctx, group):
    for name, _node in sorted(ctx.items(*SERVER_GROUPS)):
        if _server_group_kind(ctx, name) != 'tacacs':
            ctx.unsupported(SERVER_GROUPS + (name,),
                            'AAA server group is not a TACACS/HWTACACS group; no '
                            'hwtacacs scheme is emitted for this reference section')
            continue
        base = SERVER_GROUPS + (name,)
        ctx.val(*(base + ('name',)))
        scheme_name = ctx.val(*(base + ('config', 'name')), default=name) or name
        servers = _read_servers(ctx, name)

        group.append('hwtacacs scheme %s' % scheme_name)
        common_key = _common_value(servers, 'key')
        common_vpn = _common_value(servers, 'vpn')
        common_source = _common_value(servers, 'source')

        for position, record in enumerate(servers):
            label = 'primary' if position == 0 else 'secondary'
            if position > 1:
                ctx.unsupported(record['path'],
                                'HWTACACS scheme view supports one primary and one '
                                'secondary server; additional server omitted')
                break
            suffix = _server_suffix(record, common_key, common_vpn)
            for role in HWTACACS_ROLES:
                group.append('%s %s %s%s' % (label, role, record['address'], suffix))

        if common_key is not None:
            for role in HWTACACS_ROLES:
                group.append('key %s simple %s' % (role, common_key))
        group.append('user-name-format without-domain')
        if common_source is not None:
            group.append('nas-ip %s' % common_source)
        elif servers:
            source = servers[0]['source']
            if source:
                group.append('nas-ip %s' % source)
            for record in servers[1:]:
                if record['source'] and record['source'] != source:
                    ctx.unsupported(record['path'] + ('tacacs', 'config', 'source-address'),
                                    'the scheme-level nas-ip can only carry one source '
                                    'address; this differing server source is not emitted')
        if common_vpn is not None:
            group.append('vpn-instance %s' % common_vpn)

        if servers:
            ctx.ambiguous(base + ('servers',),
                          'the OC server entries carry index and priority but no explicit '
                          'primary/secondary role',
                          'servers are ordered by ascending index (highest priority '
                          'first); the first server becomes primary and the second '
                          'secondary for all three HWTACACS roles')
            ctx.ambiguous(base + ('servers',),
                          'the reference omits the TCP port although the OC document '
                          'stores tcp-port %s' % DEFAULT_HWTACACS_PORT,
                          'a tcp-port equal to the HWTACACS default (%s) is not '
                          'emitted' % DEFAULT_HWTACACS_PORT)
            ctx.ambiguous(base + ('servers',),
                          'the OC TACACS server entry has a single shared key and source '
                          'address for authentication, authorization and accounting',
                          'the same key is emitted for all three service roles; a common '
                          'source address becomes the scheme-level nas-ip and a common '
                          'VPN becomes the scheme-level vpn-instance')
            ctx.ambiguous(base + ('servers',),
                          'the reference stores the HWTACACS shared key with the '
                          "'simple' keyword",
                          'the OC secret-key is emitted as clear text after key <role> '
                          'simple')


# -------------------------------------------------------------------- domain
def _event_table(ctx, kind):
    base = AAA + (kind, 'events', 'event')
    events = {}
    for event, _node in sorted(ctx.items(*base)):
        ebase = base + (event,)
        ctx.val(*(ebase + ('event-type',)))
        event_type = ctx.val(*(ebase + ('config', 'event-type'))) or event
        events[event_type] = ebase
    return events


def _method_values(ctx, event_base, attribute):
    node = ctx.dig(*(event_base + ('config', attribute)))
    values = []
    if isinstance(node, list):
        for index in range(len(node)):
            value = ctx.val(*(event_base + ('config', attribute, str(index))))
            if value is not None:
                values.append(value)
    elif node is not None:
        value = ctx.val(*(event_base + ('config', attribute)))
        if value is not None:
            values.append(value)
    return values


def _method_tokens(ctx, event_base, attribute):
    tokens = []
    for value in _method_values(ctx, event_base, attribute):
        if value in ('local', 'none'):
            tokens.append(value)
            continue
        kind = _server_group_kind(ctx, value)
        if kind == 'tacacs':
            tokens.append('hwtacacs-scheme %s' % value)
        elif kind == 'radius':
            tokens.append('radius-scheme %s' % value)
        else:
            ctx.unsupported(event_base + ('config', attribute),
                            'AAA method %r does not name a TACACS or RADIUS server group'
                            % value)
    return tokens


def _login_tokens(ctx, events, kind, fallback):
    if 'login' in events:
        return _method_tokens(ctx, events['login'],
                              METHOD_ATTRIBUTES[kind])
    if fallback:
        ctx.ambiguous(AAA + (kind, 'events'),
                      'the OC document has no %s login event' % kind,
                      'the authentication login method chain is repeated for %s login'
                      % kind)
    return list(fallback)


def _emit_domain(ctx, group):
    domain = ctx.val('system', 'config', 'domain-name')

    auth_events = _event_table(ctx, 'authentication')
    authz_events = _event_table(ctx, 'authorization')
    acct_events = _event_table(ctx, 'accounting')

    auth_login = (_method_tokens(ctx, auth_events['login'],
                                 METHOD_ATTRIBUTES['authentication'])
                  if 'login' in auth_events else [])
    authz_login = _login_tokens(ctx, authz_events, 'authorization', auth_login)
    acct_login = _login_tokens(ctx, acct_events, 'accounting', auth_login)

    authz_command = (_method_tokens(ctx, authz_events['command'],
                                    METHOD_ATTRIBUTES['authorization'])
                     if 'command' in authz_events else [])
    acct_command = (_method_tokens(ctx, acct_events['command'],
                                   METHOD_ATTRIBUTES['accounting'])
                    if 'command' in acct_events else [])

    if not domain:
        return

    group.append('domain name %s' % domain)
    if auth_login:
        group.append('authentication login %s' % ' '.join(auth_login))
    if authz_login:
        group.append('authorization login %s' % ' '.join(authz_login))
    if acct_login:
        group.append('accounting login %s' % ' '.join(acct_login))
    if authz_command:
        if not any(token in ('local', 'none') for token in authz_command):
            authz_command.append('none')
            ctx.ambiguous(authz_events['command'] + ('config', 'authorization-method'),
                          'the OC command-authorization method list has no local/none '
                          'fallback entry',
                          "the reference terminates the method chain with the fixed "
                          "'none' fallback; appended when no local/none entry exists")
        group.append('authorization command %s' % ' '.join(authz_command))
    if acct_command:
        emitted = [token for token in acct_command
                   if token.startswith('hwtacacs-scheme')]
        if len(emitted) != len(acct_command):
            ctx.unsupported(acct_events['command'] + ('config', 'accounting-method'),
                            'accounting command only accepts a hwtacacs-scheme method; '
                            'other method types are not representable')
        if emitted:
            group.append('accounting command %s' % ' '.join(emitted))

    group.append('domain default enable %s' % domain)
    ctx.ambiguous(('system', 'config', 'domain-name'),
                  'the OC document carries a single ISP domain name but no explicit '
                  'default-domain flag',
                  'the configured domain-name is treated as the device default ISP '
                  'domain and emitted with domain default enable')
    group.append('domain name system')
    group.append('state block')
    ctx.ambiguous(AAA,
                  'the reference configures and blocks the built-in ISP domain "system"; '
                  'the OC document cannot express a second, preset ISP domain or its '
                  'state',
                  "the fixed 'domain name system' / 'state block' pair is reproduced")


# ---------------------------------------------------------------------- main
def _report_unmapped(ctx):
    if ctx.dig(*AAA, 'authentication', 'admin-user', 'config', 'admin-password') is not None:
        ctx.ignored(AAA + ('authentication', 'admin-user'),
                    'administrator password has no separate CLI line in the reference '
                    'AAA section; the local-user password carries the credential')


def emit_aaa(ctx):
    group = ctx.group()
    _report_unmapped(ctx)

    for line in PASSWORD_CONTROL_UNDO:
        group.append(line)
    ctx.ambiguous(AAA,
                  'the OC document does not model the password-control policy',
                  'the reference disables the five password-control features with fixed '
                  'undo commands, reproduced in the reference order')

    users = _read_local_users(ctx)
    _emit_local_users(ctx, group, users)
    _emit_ssh_users(ctx, group, users)
    _emit_hwtacacs(ctx, group)
    _emit_domain(ctx, group)
