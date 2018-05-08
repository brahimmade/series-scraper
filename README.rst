============
Series Scraper
============
Tool that extracts links from serienjunkies.org of TV show episodes that are still missing in your Plex library.

Usage
============
1. Clone repository
2. Install dependencies using pip:

.. code-block:: bash

    $ pip install -r requirements.txt

3. Copy config.example, fill in configuration values and rename new file to config.yaml
4. Start with scrapy crawl serienjunkies_spider

You might run into issues when installing the requirements on Windows, due to the PyCrypto dependency of the MyJDownloader API.
See: https://github.com/dlitz/pycrypto/issues/218

Contributing
============
1. Fork the repository
2. Create your own feature branch
3. Commit changes
4. Push to branch
5. Create pull request

`Click here to learn more about pull requests.`_

.. _`Click here to learn more about pull requests.`: https://guides.github.com/introduction/flow/