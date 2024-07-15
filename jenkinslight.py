'''
    Ugh. Module
'''

import json
from typing import Any

from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.parse import quote as urlquote
from urllib.parse import urlencode

from requests import HTTPError, ConnectionError

from jenkinsapi.utils.requester import Requester


class JenkinsLight():

    def __init__(
        self,
        baseurl: str,
        username: str = "",
        password: str = "",
        requester=None,
        ssl_verify: bool = True,
        cert=None,
        timeout: int = 10,
        max_retries=None,
    ) -> None:
        """
        :param baseurl: baseurl for jenkins instance including port, str
        :param username: username for jenkins auth, str
        :param password: password for jenkins auth, str
        :return: a Jenkins obj
        """
        self.username = username
        self.password = password
        self.baseurl = baseurl
        if requester is None:
            requester = Requester

            self.requester = requester(
                username,
                password,
                baseurl=baseurl,
                ssl_verify=ssl_verify,
                cert=cert,
                timeout=timeout,
                max_retries=max_retries,
            )
        else:
            self.requester = requester


    def get_janka_pipeline_data(self, jobname, filename):
        """_summary_

        Args:
            j (_type_): _description_
            jobname (_type_): _description_
            filename (_type_): _description_

        Returns:
            _type_: _description_
        """    
        data = None
        url = self.baseurl + '/job/' + jobname + '/wfapi/runs'
        # print(f'pipeline url {url}')
        requester = self.requester

        response = requester.get_url(url)

        content: Any = response.content

        if isinstance(content, str):
            data = content
        elif isinstance(content, bytes):
            data = content.decode(response.encoding or "ISO-8859-1")

        if response.status_code != 200:
            logger.error(
                "Failed request at %s with params: %s %s",
                url,
                None,
                "",
            )
            response.raise_for_status()

        json_data = json.loads(data)

        if filename is not None:
            j = json.dumps(json_data, indent=4, ensure_ascii=False)
            with open(filename, 'w', encoding="utf-8") as output_file:
                output_file.write(j)

        return json_data

