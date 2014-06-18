postfix-maps-from-ldap
======================

script to create postfix email maps for alias and/or smtp_generic_maps from ldap cross indexing on account name (gecos)

Intended to be run from cron regularly.

postfix needs to be set up in main.cf along the lines of:

```
alias_maps = hash:/etc/aliases, hash:/etc/aliases.ldap
alias_database = hash:/etc/aliases, hash:/etc/aliases.ldap
smtp_generic_maps = hash:/etc/aliases.ldap
```

This allows a Unix box behind the firewall with one set of account names to send from LDAP specified 
email addresses, and forward on when a local email is received.
It needs the Unix account name (gecos field) to match the LDAP displayName.

There are a number of handy for specific case config options documented in more detail in the example ini file, which is also displayed as the help text.

One important current limitation is that this script currently only works for accounts with primary group id 200! This can be changed in the source, and soon should be a config option.

