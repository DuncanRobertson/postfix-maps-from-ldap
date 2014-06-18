#!/usr/bin/python
#
import ldap, pprint, fileinput, sys, time, os, ConfigParser

#
# crossindexes non locked Pronto user accounts with LDAP user info to generate a list of valid email addresses
# for use in some Postfix lookup tables so Pronto is emailing To: and From: sane email addresses where possible.
#

reconciledemails = {}

# fixed text placed at the top of the generated aliases file so people know not to edit it.
preamble = '''#
# this file is generated by the script %s
#
# generated on date %s
#
# DO NOT EDIT BY HAND!
# instead check the script to see whats going on
#
# it is used by poscript for alias mapping (To: email mapping)
# and smtp_generic_maps (From: email mapping)
# so pronto user ids and the actual email addresses match.
#
#
''' % (sys.argv[0],time.ctime())

def getemail(name,l,base):

    global Messaging_EmailAddresses

    l.protocol_version = ldap.VERSION3
    l.set_option(ldap.OPT_REFERRALS, 0)
 
    criteria =   "(&(objectClass=*)(displayName=%s))" % name
    attributes = ['mail',Messaging_EmailAddresses]
    result = l.search_s(base, ldap.SCOPE_SUBTREE, criteria, attributes)
 
    results = [entry for dn, entry in result if isinstance(entry, dict)]

    # this bit checks if we returned an org specficic Messaging-EmailAddresses result,
    # and finds the primary SMTP address, which is capitalised. 
    # otherwise the email addres in the normal LDAP field is returned.
    if results != [] and results[0].has_key(Messaging_EmailAddresses):
       for companyspecificaddress in results[0][Messaging_EmailAddresses]:
          # print name, companyspecificaddress.split(":")
          if companyspecificaddress.split(":")[0] == "SMTP":
             # print "found primary address in org specific Messaging-EmailAddresses attrib", companyspecificaddress.split(":")[1]
             return companyspecificaddress.split(":")[1]
    else:
       # print name, ": no org specific Messaging-EmailAddresses attrib"
       pass 
    try:
       return results[0]['mail'][0]
    except:
       return None

def reconcileagainstldap(serverurl,usernname,password,base,names):
   unreconciled = {}
   global reconciledemails
   l = ldap.initialize(serverurl)
   bind = l.simple_bind_s(usernname,password)

   for name in names:
      email = getemail(name,l,base)
      if email == None:
         # print "Couldnt find email for ",name
         unreconciled[name] = names[name]
      else:
         # print "Found email ", email, " for ",name,names[name]
         reconciledemails[names[name]] = email

   l.unbind()
   return unreconciled


settings = ConfigParser.ConfigParser()
try:
   settings.read(sys.argv[1])
except:
   print "Need to specify config ini file on command line, i.e."
   print sys.argv[0]," configfile.ini"
   print '''Config file has format like (here is an example):

=============================================================
# section named config is general config, rest are LDAP servers to contact
# with parameters needed for them
[config]
reloadpostfix = /usr/bin/newaliases; sleep 1; /usr/sbin/postfix reload
aliasfile = /etc/aliases.ldap
passwdfile = /etc/passwd
shadowfile = /etc/shadow
# list of unix logins to be excluded from the lookup.
nonldapusers  = user1 user2 user3

# optional: forcing a rewrite of the file if it changes length by more than 10%
force_write = yes

# optional if the org has a non standard additional attribute containing a list of email addresses 
# that need to be looked at as well.... (looks for the one starting with "SMTP:x@y.com" in caps..
Messaging-EmailAddresses = companyname-Messaging-EmailAddresses

# sections not called config are presumed to have ldap config info and are
# processed in alphabetical order, so fastest responding servers can be put first
[A SERVER]
server = ldap://xyz.com
username = ldap@xyz.com
password = abc123
base = DC=xyz,DC=com

[B SERVER]
server = ldap://192.168.1.2
username = aaa@xxx.co.uk
password = abc123
base = OU=Users,OU=Exchange,DC=xxx,DC=co,DC=uk
=============================================================
'''
   sys.exit(1)

sections = settings.sections()
if "config" not in sections:
   print "config file needs [config] section with global config"
   sys.exit(1)

# turn section list into list of ldap servers
sections.remove("config")

# get the nonldap users
if settings.has_option('config','nonldapusers'):
   nonldapusers = settings.get('config','nonldapusers').split()
else:
   nonldapusers = []

if settings.has_option('config','forcewrite'):
   force_write = settings.getboolean(thesection,'force_write')
else:
   force_write = False;

#
# Org specific Email-Addresses attribute that may override the more standard "mail" attribute.
#
if settings.has_option('config','Messaging-EmailAddresses'):
   Messaging_EmailAddresses = settings.get('config','Messaging-EmailAddresses')
else:
   Messaging_EmailAddresses = "Messaging-EmailAddresses-Attribute-Not-Set-To-Anything-We-Will-Ever-Find"

aliasfile = settings.get('config','aliasfile')

# get the number of lines in aliasfile already
currentaliaseslength = len(open(aliasfile).readlines())
#
# get list of lockedlogins
#

lockedlogins = [] 
for line in fileinput.input(settings.get('config','shadowfile')):
   shadowline = line.strip().split(":")
   if shadowline[1][:2] == '!!' or shadowline[1] == '*LK*':
      lockedlogins.append(shadowline[0])

#
# read user names from /etc/passwd in passwd format
# dont include those not in pronto group (200) or 
# those that are locked (determined from shadow), convert to lower case..
#
names = {}
for line in fileinput.input(settings.get('config','passwdfile')):
   passwdline = line.strip().split(":")
   # only care if in pronto group or not locked, or the ones not in the ignore list
   if passwdline[3] == '200' and not passwdline[0] in lockedlogins and not passwdline[0] in nonldapusers:
      names[passwdline[4].lower()] = passwdline[0]

notreconciledyet = names

# access the sections in alphabetical order, gives as some control for putting
# the slow ones last
sections.sort()

for ldapserv in sections:
   notreconciledyet = reconcileagainstldap(settings.get(ldapserv,'server'),
                                           settings.get(ldapserv,'username'),
                                           settings.get(ldapserv,'password'),
                                           settings.get(ldapserv,'base'),
                                           notreconciledyet)
   print len(notreconciledyet), "accounts not reconciled after checking ldap server",settings.get(ldapserv,'server')

for name in notreconciledyet:
         print "user: couldnt reconcile with ldap: %s,%s" % (name,notreconciledyet[name])

logins = reconciledemails.keys()
logins.sort()
print "we got ",len(logins)," email addresses crossindexed from the pronto userids."
if len(logins) + len(preamble.split('\n')) > currentaliaseslength * 0.9 or force_write:
   writefile = open(aliasfile,"w")
   writefile.write(preamble)
   for login in logins:
      writefile.write(login+':\t\t'+reconciledemails[login]+'\n')
   writefile.close()
   # run commands to reload postfix config
   print "writing new file ",aliasfile," and telling postfix"
   os.system(settings.get('config','reloadpostfix'))
else:
   print "not overwriting as the new file is smaller than the old one by more than 10%% (%d lines versus %d lines)" % (currentaliaseslength,len(logins) + len
(preamble.split('\n')))
