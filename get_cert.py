#!/usr/bin/env python3
# Needs `pip3 install dnspython`
import dns.resolver
# Regular imports that didn't need pip
import getopt
import logging
import os
import requests
import subprocess
import sys
import time

# Used for debugging CNAME requests
# Needs `pip3 install requests_toolbelt`
# from requests_toolbelt.utils import dump

# Exit codes:
# 1 API tokens not set in env variables
# 2 Incorrect command line arguments
# 3 Drafting certificate failed
# 4 Adding CNAME failed
# 5 Waited too long for DNS propagation
# 6 Certificate validation failed
# 7 Certificate not ready to download

# Get API tokens from environment variables
do_token = os.getenv('DO_KEY')
zerossl_token = os.getenv('ZEROSSL_KEY')
if do_token == '' :
    print("Digital Ocean API key not defined in env variable DO_KEY")
    sys.exit(1)
elif zerossl_token == '':
    print("ZeroSSL API key not defined in env variable ZEROSSL_KEY")
    sys.exit(1)

# Set base URLs for APIs
do_base = 'https://api.digitalocean.com/v2/'
zerossl_base = 'https://api.zerossl.com/'

# Set headers for Digital Ocean
do_headers = {'Content-Type': 'application/json',
              'Authorization': f'Bearer {do_token}'}

def getopts(argv):
    verbose = False
    try:
        opts, args = getopt.getopt(argv,"hc:d:v",["certname=","domain=","verbose"])
    except getopt.GetoptError:
        print('Incorrect arguments. Use: get_cert.py -c <cert_name> -d <domain>')
        sys.exit(2)
    if len(opts):
        for opt, arg in opts:
            if opt == '-h':
                print ('get_cert.py -c <cert_name> -d <domain>')
                sys.exit()
            elif opt in ("-c", "--certname"):
                cert_name = arg
            elif opt in ("-d", "--domain"):
                base_domain = arg
            elif opt in ("-v", "--verbose"):
                verbose = True
    else:
        print('No arguments passed. Use: get_cert.py -c <cert_name> -d <domain>')
        sys.exit(2)
    return (cert_name,base_domain,verbose)

def draft_cert():
    mylogs.info('Drafting certificate')
    api_url = f'{zerossl_base}certificates?access_key={zerossl_token}'
    # Read CSR file into variable and strip out newlines
    with open(f'{cert_name}.csr', 'r') as csr:
        csr_content = csr.read().replace('\n', '')
    cert_params = {'certificate_validity_days' : '90',
        'certificate_domains' : cert_name,
        'certificate_csr' : csr_content}
    cert_req = requests.post(api_url, data=cert_params)
    
    resp_file = open(f'{cert_name}.resp', 'w')
    resp_file.write(cert_req.text)
    resp_file.close()
    if 'id' not in cert_req.json():
        mylogs.warning(f'Drafting certificate failed\n{cert_req.text}')
        sys.exit(3)
    else:
        cert_id=cert_req.json()['id']
        mylogs.info(f'Certificate ID is: {cert_id}')    
        cname_host=(cert_req.json()['validation']['other_methods'][f'{cert_name}']['cname_validation_p1']).replace(f'.{base_domain}','')
        mylogs.info(f'CNAME host is: {cname_host}')
        cname_value=cert_req.json()['validation']['other_methods'][f'{cert_name}']['cname_validation_p2']
        mylogs.info(f'CNAME value is: {cname_value}')
        return(cert_id,cname_host,cname_value)

def create_cname():
    mylogs.info('Creating CNAME')
    api_url = f'{do_base}domains/{base_domain}/records'

    cname_params = {'type' : 'CNAME', 'name' : f'{cname_host.lower()}',
        'data' : f'{cname_value.lower()}.', 'ttl' : 1800}
    cname_add = requests.post(api_url, headers=do_headers, json=cname_params)

    name_file = open(f'{cert_name}.name', 'w')
    name_file.write(f'{cname_host}{os.linesep}')
    name_file.write(f'{cname_value}{os.linesep}')
    #name_file.write(dump.dump_all(cname_add).decode("utf-8"))
    name_file.write(cname_add.text)
    name_file.close()
    if 'domain_record' not in cname_add.json():
        mylogs.warning(f'Adding CNAME failed\n{cname_add.text}')
        sys.exit(4)
    else:    
        cname_id=cname_add.json()['domain_record']['id']
        mylogs.info(f'Created CNAME ID: {cname_id}')
        return(cname_id)

def test_cname():
    mylogs.info('Testing CNAME')
    cname_propagated='false'
    wait_time=10
    dns_resolver=dns.resolver.Resolver()
    while cname_propagated == 'false':
        try:
            dnslookup = dns_resolver.resolve(f'{cname_host}.{base_domain}', 'CNAME')
        except Exception as e:
            print(e)
            dnslookup = ''
        if len(dnslookup):
            mylogs.info(f'CNAME found: {dnslookup}')
            cname_propagated='true'
        else:
            mylogs.info('Waiting for ',wait_time)
            time.sleep(wait_time)
            wait_time=wait_time*2
            if wait_time > 320:
                mylogs.warning('Waited too long for DNS')
                print('Waited too long for DNS')
                sys.exit(5)

def validate_cert(retry):
    mylogs.info('Validating certificate')
    retries=retry+1

    api_url = f'{zerossl_base}certificates/{cert_id}/challenges?access_key={zerossl_token}'
    
    cert_vald = requests.post(api_url, data={'validation_method' : 'CNAME_CSR_HASH'})
    
    if 'id' not in cert_vald.json():
        if retries == 6:
            mylogs.warning(f'Certificate validation failed\n{cert_vald.text}')
            sys.exit(6)
        else:
            mylogs.info(f'Retry {retries} for {cert_name}' )
            time.sleep(10^retries)
            validate_cert(retries)
    
    resp_file = open(f'{cert_name}.vald', 'w')
    resp_file.write(cert_vald.text)
    resp_file.close()

def check_cert():
    mylogs.info('Checking certificate')
    api_url = f'{zerossl_base}certificates/{cert_id}?access_key={zerossl_token}'

    cert_issued='false'
    wait_time=10
    while cert_issued == 'false':
        cert_verf = requests.get(api_url)
        if cert_verf.json()['status'] == 'issued':
            mylogs.info('Cert is ready to download')
            cert_issued='true'
        else:
            mylogs.info(f'Waiting for {wait_time}')
            time.sleep(wait_time)
            wait_time=wait_time*2
            if wait_time > 320:
                mylogs.warning('Waited too long for cert to be issued')
                sys.exit(7)
    
def get_cert():
    mylogs.info('Downloading certificate')
    api_url = f'{zerossl_base}certificates/{cert_id}/download/return?access_key={zerossl_token}'

    cert = requests.get(api_url)

    cert_file = open(f'{cert_name}.crt', 'w')
    cert_file.write(cert.json()['certificate.crt'])
    cert_file.close()

    ca_file = open(f'{cert_name}.cas', 'w')
    ca_file.write(cert.json()['ca_bundle.crt'])
    ca_file.close()

def delete_cname():
    logging.info('Deleting CNAME')
    api_url = f'{do_base}domains/{base_domain}/records/{cname_id}'

    requests.delete(api_url, headers=do_headers)
    
# Extract base_domain and cert_name from command line options
cli_opts=getopts(sys.argv[1:])
base_domain=cli_opts[1]
cert_name=cli_opts[0]+'.'+base_domain
verbose=cli_opts[2]

# Setup logging
mylogs = logging.getLogger(__name__)
mylogs.setLevel(logging.DEBUG)

logformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")

logfile = logging.FileHandler(f'{cert_name}.log')
logfile.setLevel(logging.INFO)
logfile.setFormatter(logformat)

mylogs.addHandler(logfile)

logstream = logging.StreamHandler()
if verbose:
    logstream.setLevel(logging.INFO)
else:
    logstream.setLevel(logging.WARN)
logstream.setFormatter(logformat)

mylogs.addHandler(logstream)

# Generate a Certificate Signing Request (CSR) using OpenSSL
mylogs.info(f'Creating CSR {cert_name}.csr')
try: 
    generate_csr = subprocess.run(['openssl','req','-new','-newkey','rsa:2048','-nodes',
    '-out',f'{cert_name}.csr','-keyout',f'{cert_name}.key',
    '-subj',f'/CN={cert_name}'],
    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    mylogs.warning(f'CSR generation failed {e.output}')

# Draft a certificate and extract id and cname parameters from response
cert_details=draft_cert()
cert_id=cert_details[0]
cname_host=cert_details[1]
cname_value=cert_details[2]

# Add DNS CNAME for validation
cname_id=create_cname()

# Test for propogation of CNAME
test_cname()

# Validate certificate
validate_cert(0)

# Check certificate available
check_cert()

# Download certificate
get_cert()

# Tidy up CNAME
delete_cname()