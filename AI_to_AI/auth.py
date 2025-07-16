import os 
import sys
import requests

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from sesame_ai import SesameAI, TokenManager

# remove proxy conf to use the vpn tunnel since it is request under the hood
# sudo openvpn --config /mnt/nas/KITT/scrap/fr555.nordvpn.com.tcp.ovpn
# curl ipinfo.io --noproxy '*'

os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)

response = requests.get('https://api.ipify.org')
print("Public IP via Python:", response.text)



print("removing token 0")
os.remove("token0.json")

print("removing token 1")
os.remove("token1.json")


for i in range(2):
    # Create API client
    client = SesameAI()

    # Create an anonymous account
    signup_response = client.create_anonymous_account()
    print(f"ID Token: {signup_response.id_token}")

    # Look up account information
    lookup_response = client.get_account_info(signup_response.id_token)
    print(f"User ID: {lookup_response.local_id}")

    # For easier token management, use TokenManager
    token_manager = TokenManager(client, token_file=f"token{i}.json")
    id_token = token_manager.get_valid_token()