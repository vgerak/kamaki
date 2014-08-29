# Copyright 2014 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from kamaki.cli.config import Config
from kamaki.clients import astakos, pithos, ClientError

cnf = Config()
CLOUD = cnf.get('global', 'default_cloud')
URL = cnf.get_cloud(CLOUD, 'url')
TOKEN = cnf.get_cloud(CLOUD, 'token')
identity_client = astakos.AstakosClient(URL, TOKEN)

pithosURL = identity_client.get_endpoint_url(pithos.PithosClient.service_type)
storage_client = pithos.PithosClient(pithosURL, TOKEN)
storage_client.account = identity_client.user_info['id']
storage_client.container = 'pithos'

import time

backup_container = 'backup_%s' % time.time()
storage_client.create_container(backup_container)

for o in storage_client.list_objects():
    try:
        storage_client.copy_object(
            storage_client.container, o['name'], backup_container)
    except ClientError as ce:
        print "Failed to backup object %s" % o['name']
        print ce
