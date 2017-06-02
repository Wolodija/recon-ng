from recon.core.module import BaseModule
import re
import requests
# ToDo: Make more intelligent redirecting (check status code and later location)
# ToDo: Captcha
# ToDo: Tests
# ToDo: Refactor: mainly split on multiple functions


class Module(BaseModule):

    meta = {
        'name': 'Goldenline Authenticated Contact Enumerator',
        'author': 'Pawel Nogiec, Dominik Rosiek, Daniel Slusarczyk',
        'description': 'Harvests contacts from the goldenline.pl API using an authenticated connections network. Updates the \'contacts\' table with the results.',
        'required_keys': ['goldenline_username', 'goldenline_password'],
        'query': 'SELECT DISTINCT company FROM companies WHERE company IS NOT NULL',
    }

    def get_goldenline_url(self, url):
        """
        Process Url
        @param url:
        @return:
        """
        if url.startswith("https"):
            return url
        else:
            return 'https://www.goldenline.pl' + url

    def get_goldenline_access_token(self, s):
        """
        Get goldenline access token by authenticating to api hal-browser

        @return:
         str
        """
        url = 'https://www.goldenline.pl/aplikacja/hal-browser/'
        response = s.get(url, allow_redirects=False)
        if response.status_code != 302:
            return

        # hal-browser/connect
        url = self.get_goldenline_url(response.headers.get('Location'))
        response = s.get(url, allow_redirects=False)

        # oauth
        url = self.get_goldenline_url(response.headers.get('Location'))
        response = s.get(url, allow_redirects=False)
        #login
        url = self.get_goldenline_url(response.headers.get('Location'))
        response = s.get(url, allow_redirects=False)

        username = self.get_key('goldenline_username')
        password = self.get_key('goldenline_password')

        data = {
            'login': username,
            'password': password
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = s.post(url, data, headers=headers, allow_redirects=True)
        if re.findall('fos_oauth_server_authorize',response.content).__len__() != 0:
            print 'Permission denied to Hal Browser. Go to website: https://www.goldenline.pl/aplikacja/hal-browser/ and give permission.'
            return
        token_list = re.findall('Authorization: Bearer (.*?)<', response.content)
        if token_list.__len__() == 0:
            return

        return token_list[0]

    def module_run(self, companies):
        # use recon/companies-contacts/goldenline_auth
        s = requests.Session()
        access_token = self.get_goldenline_access_token(s)
        if access_token == None:
            return
        # for company in companies:
        url = 'https://www.goldenline.pl/firmy/szukaj/?q={company}'
        for company in companies:
            response = s.get(url.format(company=company))
            if not response.ok:
                continue

            possible_companies = re.finditer('<td class="firm">.*?href="(.*?)".*?>(.*?)<.*?</td>', response.content, re.MULTILINE|re.DOTALL)

            company_ids = []
            for details in possible_companies:
                link, name = details.groups()
                if company.lower() not in name.lower():
                    continue

                resp = s.get(link)
                if not resp.ok:
                    continue

                results = re.findall("var firm = {.*?id: (.*?),.*?name: '(.*?)',.*?urlName: '(.*?)'.*?};", resp.content, re.MULTILINE|re.DOTALL)

                if not results:
                    continue

                company_ids.append(results[0][0])

        url = 'https://api.goldenline.pl/firms/{company_id}/employees?page={page}'
        max_page = 1
        page = 0

        headers = {
            'Authorization': "Bearer {access_token}".format(access_token=access_token)
        }
        for company_id in company_ids:
            while page <= max_page:
                page += 1
                response = requests.get(url.format(company_id=company_id, page=page), headers=headers)
                results = response.json()
                max_page = int(re.findall('page=(\d+)', results.get('_links', {}).get('last').get('href'))[0])
                employees = results.get('_embedded', {}).get('employee', [])
                for employee in employees:
                    self.add_contacts(first_name=employee.get('name'), last_name=employee.get('surname'),
                                      title=employee.get('position'), region='PL', country='Poland')
