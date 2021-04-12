#!/usr/bin/python3
# Needs `pip3 install dnspython`
import dns.resolver
# Regular imports that didn't need pip
import getopt
import json
import os
import requests
import subprocess
import sys
import time

# Used for debugging CNAME requests
# Needs `pip3 install requests_toolbelt`
#from requests_toolbelt.utils import dump

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
elif zerossl_token == "":
    print("ZeroSSL API key not defined in env variable ZEROSSL_KEY")
    sys.exit(1)

# Set base URLs for APIs
do_base = 'https://api.digitalocean.com/v2/'
zerossl_base = 'https://api.zerossl.com/'

# Set headers for Digital Ocean
do_headers = {'Content-Type': 'application/json',
              'Authorization': f'Bearer {do_token}'}

def getopts(argv):
    try:
        opts = getopt.getopt(argv,"hc:d:",["certname=","domain="])
    except getopt.GetoptError:
        print('Incorrect arguments. Use: cert_cert.py -c <cert_name> -d <domain>')
        sys.exit(2)
    if len(opts):
        for opt, arg in opts:
            if opt == '-h':
                print ('cert_cert.py -c <cert_name> -d <domain>')
                sys.exit()
            elif opt in ("-c", "--certname"):
                cert_name = arg
            elif opt in ("-d", "--domain"):
                base_domain = arg
    else:
        print('No arguments passed. Use: cert_cert.py -c <cert_name> -d <domain>')
        sys.exit(2)
    return (cert_name,base_domain)

def draft_cert():
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
        print('Drafting certificate failed')
        print(cert_req.text)
        sys.exit(3)
    else:    
        cert_id=cert_req.json()['id']
        cname_host=(cert_req.json()['validation']['other_methods'][f'{cert_name}']['cname_validation_p1']).replace(f'.{base_domain}','')
        cname_value=cert_req.json()['validation']['other_methods'][f'{cert_name}']['cname_validation_p2']
        return(cert_id,cname_host,cname_value)

def create_cname():
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
        print('Adding CNAME failed')
        print(cname_add.text)
        sys.exit(4)
    else:    
        cname_id=cname_add.json()['domain_record']['id']
        return(cname_id)

def test_cname():
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
            #print ('CNAME found:', dnslookup)
            cname_propagated='true'
        else:
            print('Waiting for ',wait_time)
            time.sleep(wait_time)
            wait_time=wait_time*2
            if wait_time > 320:
                print('Waited too long for DNS')
                sys.exit(5)

def validate_cert(retry):
    retries=retry+1

    api_url = f'{zerossl_base}certificates/{cert_id}/challenges?access_key={zerossl_token}'
    
    cert_vald = requests.post(api_url, data={'validation_method' : 'CNAME_CSR_HASH'})
    
    if 'id' not in cert_vald.json():
        if retries == 6:
            print('Certificate validation failed')
            print(cert_vald.text)
            sys.exit(6)
        else:
            print(f'Retry {retries} for {cert_name}' )
            print(cert_vald.text)
            time.sleep(10^retries)
            validate_cert(retries)
    
    resp_file = open(f'{cert_name}.vald', 'w')
    resp_file.write(cert_vald.text)
    resp_file.close()

def check_cert():
    api_url = f'{zerossl_base}certificates/{cert_id}?access_key={zerossl_token}'

    cert_issued='false'
    wait_time=10
    while cert_issued == 'false':
        cert_verf = requests.get(api_url)
        if cert_verf.json()['status'] == 'issued':
            #print ('Cert is ready to download')
            cert_issued='true'
        else:
            #print('Waiting for ',wait_time)
            time.sleep(wait_time)
            wait_time=wait_time*2
            if wait_time > 320:
                print('Waited too long for cert to be issued')
                sys.exit(7)
    
def get_cert():
    api_url = f'{zerossl_base}certificates/{cert_id}/download/return?access_key={zerossl_token}'

    cert = requests.get(api_url)

    cert_file = open(f'{cert_name}.crt', 'w')
    cert_file.write(cert.json()['certificate.crt'])
    cert_file.close()

def delete_cname():
    api_url = f'{do_base}domains/{base_domain}/records/{cname_id}'

    cname_del = requests.delete(api_url, headers=do_headers)
    
# Extract base_domain and cert_name from command line options
cli_opts=getopts(sys.argv[1:])
base_domain=cli_opts[1]
cert_name=cli_opts[0]+'.'+base_domain

# Generate a Certificate Signing Request (CSR) using OpenSSL
try: 
    generate_csr = subprocess.run(['openssl','req','-new','-newkey','rsa:2048','-nodes',
    '-out',f'{cert_name}.csr','-keyout',f'{cert_name}.key',
    '-subj',f'/C=GB/ST=London/L=London/O=Example/OU=Testing/CN={cert_name}'],
    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    print(generate_csr)
    print(e.output)

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
