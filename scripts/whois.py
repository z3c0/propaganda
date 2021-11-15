import os
import re
import pprint as pp
import subprocess

from top_level_domain_regex import TopLevelDomainRegExp


def _create_top_level_domain_map():
    tld_regex = dict()

    def get_top_lvl_domain_re(top_lvl_dmn: str):
        if top_lvl_dmn in tld_regex:
            return tld_regex[top_lvl_dmn]

        if top_lvl_dmn == 'in':
            return 'in_'

        patterns = getattr(TopLevelDomainRegExp, top_lvl_dmn)
        extend = patterns.get('extend')
        if extend:
            extend_val = get_top_lvl_domain_re(extend)
            swap = extend_val.copy()
            swap.update(patterns)
        else:
            swap = patterns

        if 'extend' in swap:
            del swap['extend']

        swap_dict = dict()
        for key, value in swap.items():
            value = (re.compile(value, re.IGNORECASE)
                     if isinstance(value, str) else value)
            swap_dict[key] = value

        tld_regex[top_lvl_dmn] = swap_dict

        return tld_regex[top_lvl_dmn]

    for top_level_domain in dir(TopLevelDomainRegExp):
        if top_level_domain[0] != '_':
            get_top_lvl_domain_re(top_level_domain)

    return tld_regex


def _check_whois_text_for_dnssec(output: str):
    dnssec = output.split('DNSSEC:')
    if len(dnssec) == 1:
        return False

    dnssec = dnssec[1].split('\n')[0].strip()

    return dnssec == 'signedDelegation' or dnssec == 'yes'


def _check_whois_text_for_errors(output):
    if output.count('\n') >= 5:
        return output

    if output == 'not found':
        return None

    if output.startswith('no such domain'):
        return None

    if output.count('error'):
        return None

    raise Exception(f'Failed to parse whois text:\n{output}')


def _parse_domain(url: str):
    domain = url.split('.')

    if domain[0] == 'www':
        domain = domain[1:]
    if len(domain) == 1:
        return None

    if url.endswith('.ac.uk') and len(domain) > 2:
        top_level_domain = 'ac_uk'
    elif url.endswith('co.il') and len(domain) > 2:
        top_level_domain = 'co_il'
    elif url.endswith('.co.jp') and len(domain) > 2:
        top_level_domain = 'co_jp'
    elif url.endswith('.com.au') and len(domain) > 2:
        top_level_domain = 'com_au'
    elif url.endswith('com.tr') and len(domain) > 2:
        top_level_domain = 'com_tr'
    elif url.endswith('global'):
        top_level_domain = 'global_'
    elif url.endswith('.id'):
        top_level_domain = 'id_'
    elif url.endswith('.in'):
        top_level_domain = 'in_'
    elif url.endswith('.is'):
        top_level_domain = 'is_'
    elif url.endswith('.name'):
        domain[0] = 'domain=' + domain[0]
        top_level_domain = domain[-1]
    elif url.endswith('.xn--p1ai'):
        top_level_domain = 'ru_rf'
    else:
        top_level_domain = domain[-1]

    domain = '.'.join(domain)

    return domain, top_level_domain


def download_whois_exe():
    copy_command = 'copy \\\\live.sysinternals.com\\tools\\whois.exe .'
    subprocess.call(copy_command, shell=True)


def whois(url: str):
    domain, top_level = _parse_domain(url)

    result_set = {'domain': domain,
                  'top_level_domain': top_level}

    top_level_domain_map = _create_top_level_domain_map()

    if top_level not in top_level_domain_map.keys():
        print(f'Unknown TLD: .{top_level}')
        return dict(unknown_tld=True, **result_set)

    if not os.path.exists('whois.exe'):
        download_whois_exe()

    process = subprocess.Popen([f'whois.exe', url], stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if stderr is not None:
        print(stderr)

    output = stdout.decode(errors='ignore')
    output = _check_whois_text_for_errors(output)

    has_dnssec = _check_whois_text_for_dnssec(output)

    result_set['dnssec'] = has_dnssec

    output = output.split('source:       IANA')[-1]
    server_names = re.findall(r'Server Name:\s?(.+)', output, re.IGNORECASE)

    if server_names:
        output = output[output.find('Domain Name:'):]

    dotcom_patterns = top_level_domain_map['com']
    top_level_patterns = top_level_domain_map.get(top_level, dotcom_patterns)

    print(output)

    for key, value in top_level_patterns.items():
        if value is None:
            result_set[key] = ['']
            continue

        values = value.findall(output)
        # values = [v.strip() for v in values if v.strip() != '']

        print(key, value, values)

        result_set[key] = values or ['']

    return result_set


if __name__ == '__main__':
    results = whois('morningstaronline.co.uk')
    pp.pprint(results)
