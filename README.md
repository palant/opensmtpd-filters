This is a set of scripts to simplify handling DMARC aggregate reports for low-volume email servers. Some explanations can be found in [this blog article](https://palant.info/2023/03/08/converting-incoming-emails-on-the-fly-with-opensmtpd-filters/). No support is provided, use at your own risk.

Requirements: [Jinja2](https://jinja.palletsprojects.com/intro/#installation)

`dmarc2html.py` is a command line conversion script. It takes the path to the aggregate report file as parameter and outputs HTML code.

`filter.py` is an OpenSMTPd filter process, to be used in `smtpd.conf` like this:

```
filter dmarc2html proc-exec "/opt/dmarc2html/filter.py dmarc"
```

For any email to the `dmarc@…` account (or any other account specified as command line parameter), it will process the attachment and replace the email’s main part by the resulting HTML code.