from recon.core.module import BaseModule
import requests
import re
import base64
import time
TIMEWAIT = 0.25
class Module(BaseModule):
	meta = {
		'name': 'Facebook employees finder',
		'author': 'Coenova123',
		'description': 'Get employees selected company from facebook. Updates the \'contacts\' table with the results.',
		'required_keys': ['facebook_c_user_cookie', 'facebook_xs_cookie'],
		'query': 'SELECT DISTINCT company FROM companies WHERE company IS NOT NULL',
	}
	def module_run(self, company_name):
		xs = self.keys.get('facebook_xs_cookie')
		self.c_user = self.keys.get('facebook_c_user_cookie')
		self.cookie = {'c_user': self.c_user, 'xs': xs}
		self.pattern = '(?<="_gll"><div>).*?(?=</a></div>)'
		self.pattern2 = '(?<="_gll"><div>).*?(?=<\\\\/a><\\\\/div>)'
		self.cursor_pattern_2 = '(?<=;cursor\\\\\&quot;\:\\\\\&quot;)(.*?)(?=\\\\\&quot;)'
		self.cursor_pattern_1 = '(?<=\{cursor\:")(.*?)(?="\,page_)'
		self.cursor_pattern_3 = '(?<="cursor"\:")(.*?)(?="\,"page_)'
		self.url_pattern = '(?<=<a href=")(.*?)(?=ref=br_rs")'
		self.employee_pattern = '(?<=<div class="_5d-5">)(.*?)(?=</div>)'
		self.employee_pattern_2 = '(?<=<div class="_5d-5">)(.*?)(?=/div>)'
		self.company_name_filter = '(?<=<div class="_5d-5">).*?(?=</div>)'
		self.profile_id_pattern = '(?<=data-profileid=").*?(?=<div class="_glm">)'
		self.id_filter = '(^.*?(?="))'
		self.cursor = ''
		company_list = self.get_company_id(company_name)

		if not len(company_list):
			return
		company_name, company_id = self.id_selector(company_list)
		if not company_name:
			return
		self.cursor, data = self.get_first(company_id)
		new_url = self.get_regexp_by_pattern(data, self.url_pattern).split('\n')
		new_employees = self.get_regexp_by_pattern(data, self.employee_pattern).encode('utf-8').split('\n')
		for i in xrange(len(new_employees)):
			self.add_profiles(username=new_employees[i], url=new_url[i])
			self.add_conact_by_url(new_url[i])
		iterator = 1
		while True:
			self.cursor, data = self.get_next(company_id=company_id, company_name=company_name, page_number=iterator)
			time.sleep(TIMEWAIT) # timeout 0.25 sec to avoid facebook account lockout
			new_url = self.get_regexp_by_pattern(data.replace('\/', '/'), self.url_pattern).split('\n')
			new_employees = self.get_regexp_by_pattern(data.replace('\/', '/'), self.employee_pattern).encode('utf-8').split('\n')
			for i in xrange(len(new_employees)):
				self.add_conact_by_url(new_url[i])
				self.add_profiles(username=new_employees[i], url=new_url[i])
			iterator += 1
			if len(new_url) == 1:
				break

	def add_conact_by_url(self, url):
		r = requests.get(url, cookies=self.cookie)
		name_surname = self.get_regexp_by_pattern(r.text, '(?<="Person","name":").*?(?=")')
		job_title = self.get_regexp_by_pattern(r.text, '(?<=jobTitle":").*?(?=")')
		url = self.get_regexp_by_pattern(r.text, '(?<=addressLocality":").*?(?=")')
		try:
			first_name, last_name = name_surname.split(" ")
		except ValueError:
			first_name, middle_name, last_name = name_surname.split(" ")
		try:
			region, country = url.split(", ")
		except ValueError:
			region = ""
			country = url
		self.add_contacts(first_name=first_name, last_name=last_name, title=job_title, region=region, country=country)
		time.sleep(TIMEWAIT)

	def get_company_id(self, company_name):
		params = {'filters_rp_page_supercategory': 1013}
		r = requests.get('https://www.facebook.com/search/str/' + company_name[0] + '/keywords_pages', params=params,
		                 cookies=self.cookie)
		grepped = self.get_regexp_by_pattern(r.text, self.profile_id_pattern).split('\n')
		possible_companies = []
		for company in grepped:
			name = self.get_regexp_by_pattern(company, self.company_name_filter)
			id = self.get_regexp_by_pattern(company, self.id_filter)
			possible_companies.append([name, id])
		return possible_companies

	def id_selector(self, possible_companies):
		for i in xrange(len(possible_companies)):
			print "{}: {} ({})".format(i, possible_companies[i][0].encode('utf-8').strip(), possible_companies[i][1])
		print "{}: cancel".format(len(possible_companies))
		try:
			answer = input("select company (0 - {}): ".format(len(possible_companies)))
		except:
			answer = len(possible_companies)
		if answer not in range(len(possible_companies)):
			answer = len(possible_companies)
		if answer == len(possible_companies):
			return
		return possible_companies[answer]

	def get_first(self, company_id):
		r = requests.get('https://www.facebook.com/search/' + company_id + '/employees', cookies=self.cookie)
		cursor_new = self.get_regexp_by_pattern(r.text, self.cursor_pattern_1)
		return cursor_new, self.get_regexp_by_pattern(r.text, self.pattern)

	def get_regexp_by_pattern(self, request, pattern):
		return '\n'.join(re.findall(pattern, request, flags=re.M))

	def get_next(self, company_id, company_name, page_number):
		encoded = base64.b64encode(
			'["People+who+work+at+",{"text":"' + company_name + '","uid":' + company_id + ',"type":"employer"}]')
		if encoded[-2] == '=':
			encoded = encoded[:-2]
		elif encoded[-1] == '=':
			encoded = encoded[:-1]
		output = '{"view":"list","encoded_query":"{\\"bqf\\":\\"present(employees(' + company_id + '))\\",\\"browse_sid\\":null,\\"vertical\\":\\"none\\",\\"post_search_vertical\\":null,\\"intent_data\\":null,\\"filters\\":[],\\"has_chrono_sort\\":false,\\"query_analysis\\":null,\\"subrequest_disabled\\":false,\\"token_role\\":\\"NONE\\",\\"preloaded_story_ids\\":[],\\"extra_data\\":null}","encoded_title":"' + encoded + '","ref":"unknown","logger_source":"www_main","typeahead_sid":"","tl_log":false,"impression_id":"","filter_ids":{},"experience_type":"grammar","exclude_ids":null,"browse_location":"","trending_source":null,"reaction_surface":null,"reaction_session_id":null,"ref_path":"/search/' + company_id + '/employees/present","is_trending":false,"topic_id":null,"place_id":null,"story_id":null,"callsite":"browse_ui:init_result_set","has_top_pagelet":true,"display_params":{"crct":"none"},"cursor":"' + self.cursor + '","page_number":' + str(
			page_number) + ',"em":false,"mr":false,"tr":null}'
		params = {'dpr': 1, 'data': output, '__user': self.c_user, '__a': 1}

		r2 = requests.get('https://www.facebook.com/ajax/pagelet/generic.php/BrowseScrollingSetPagelet', params=params,
		                  cookies=self.cookie)
		cursor_new = self.get_regexp_by_pattern(r2.text, self.cursor_pattern_3)
		return cursor_new, self.get_regexp_by_pattern(r2.text.decode("unicode-escape"), self.pattern2)

