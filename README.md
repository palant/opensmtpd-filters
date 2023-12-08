# Collection of various OpenSMTPD filters

This collection of OpenSMTPD filters is described in my blog posts [Adding DKIM support to OpenSMTPD with custom filters](https://palant.info/2020/11/09/adding-dkim-support-to-opensmtpd-with-custom-filters/) and [Converting incoming emails on the fly with OpenSMTPD filters](https://palant.info/2023/03/08/converting-incoming-emails-on-the-fly-with-opensmtpd-filters/). No support is provided, use at your own risk.

## Installing

These scripts are most easily installed via [pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/palant/opensmtpd-filters.git
```

Once installed, you can run the `dmarc2html-cli` command for example.

## dmarc2html

This filter helps to simplify handling of DMARC aggregate reports for low-volume email servers. It can be used in `smtpd.conf` like this:

```
filter dmarc2html proc-exec "/home/user/.local/share/pipx/venvs/opensmptd_filters/bin/dmarc2html.py dmarc"
```
For any email to the `dmarc@…` account (or any other account specified as command line parameter), it will process the attachment and replace the email’s main part by the resulting HTML code.

There is also a script that will convert a DMARC aggregate report on the command line:

```
dmarc2html-cli dmarc.tar.gz
```
