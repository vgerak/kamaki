# Copyright 2012-2013 GRNET S.A. All rights reserved.
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
# or implied, of GRNET S.A.command

from kamaki.clients.quotaholder import QuotaHolderClient
from kamaki.cli import command
from kamaki.cli.commands import _command_init


API_DESCRIPTION = dict(quotaholder='Quota Holder commands')


class _quotaholder_init(_command_init):
    def main(self):
        self.token = self.config.get('quotaholder', 'token')\
            or self.config.get('global', 'token')
        self.base_url = self.config.get('quotaholder', 'url')\
            or self.config.get('global', 'url')
        self.client = QuotaHolderClient(self.base_url, self.token)

@command()
class quotaholder_test_specific(_quotaholder_init):
    """Test quota holder commands - devel/testing only"""

    def main(self):
        super(self.__class__, self).main()
        print('We will test quota holder stuff')
        r = self.client.test_quota()
        print('That is what we got {%s}' % r)

@command()
class quotaholder_test_all(_quotaholder_init):
    """Test quota holder commands - devel/testing only"""

    def main(self):
        super(self.__class__, self).main()
        print('We will test quota holder stuff')
        r = self.client.test_quota()
        print('That is what we got {%s}' % r)

@command()
class quotaholder_test(_quotaholder_init):
    """Test quota holder commands - devel/testing only"""

    def main(self):
        super(self.__class__, self).main()
        print('We will test quota holder stuff')
        r = self.client.test_quota()
        print('That is what we got {%s}' % r)
