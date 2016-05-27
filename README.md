# Wake Up Playlist Generator
Client Authorization
------------------------------------

Client has to use full swap service as described below.

|Method|url|Description
|------|---|-----------------------
GET	|/swap|Will be called during Spotify login process. Registers or updates tokens for spotify user. This will also start generation of user’s music graph.
|GET|/refresh|Will be called by API when access token becomes invalid. Sometimes it will refresh user’s music graph but this will happen in the background.

When client is succesfully logged in and spotify session is created (see Android/iOS SDKs), it may start using API as described below.
To succesfully access API methods *Authorization* header must be present. The header consists of
refresh_token\<space>access_token
for example:
>Authorization: OSUflWFG9Ikhj2PBuJkR/A== BQC_quTfn9pi06ZogXlp62-qLDUSbQ0-0bRKpDVPTmY_FVLi0kLiWiDe1Rz3g85uV3_8fahXDj_auVdV7fCBNEhvKL99Le118C5SwNOx9_85c5bQEvEm-QZ-rEXWOX3z-tvbYJqAhoxgOLpZ5zdjf8FwuJ4661-e-cBDuyLDgP8MZFYoVV6HcyY-M9bJd-bwnNLSXQRBQx0IZEeMiDyD5H0_4BM-iIln6cnYW-M9GwX2dN-z

You can obtain refresh and access tokens in your session object (see SDK). Please note that refresh_token is an server encrypted value

Few additional remarks:
1. User needs **premium account** to use this sleep app. Free account will not give you access to play lists and streaming
2. See later on configuring Spotify App, without it you will not login
3. Refresh spotify sessions as described in SDK
4. Please provide correct spotify scope during login, please find current scope in /sleep_server/api/config.py
>playlist-read-private playlist-read-collaborative playlist-modify-private user-follow-read user-library-read user-read-private user-top-read



Api Methods
---------------------------
There are two playlist types in the API

1. *fall_asleep* will be played when user wants to sleep
2. *wake_up* will be played when user wants to wake up

All correct responses are returned with 20x HTTP status code and have following general JSON format
```javascript
{result: <content> }
```

|Method|url|Description
|------|---|-----------------------
GET|/me/playlists|Get wake up and fall asleep playlist properties
POST|/me/playlists/:playlist_type|Create/update given playlist. Should be called before playlist is accessible with GET. Calling this method will regenerate playlist content.


####/me/playlists
This method takes no parameters.
Returns list of **playlist** objects with following properties

1. **uri** spotify uri of the playlist. Use this to play music
2. **length** playlist actual length. This will be as close to desired length as possible
3. **type** (wake_up, fall_asleep)
For new users we use default desired length of **30 minutes**

Example
```javascript
curl -X GET "http://wakeupapp.dev.army/me/playlists" -H "Authorization: ...."
{
  "result": [
    {
      "length": 2203530,
      "type": "fall_asleep",
      "uri": "spotify:user:rudolfix-us:playlist:191jgxBblZ8dOAI1zis5Th"
    },
    {
      "length": 4787650,
      "type": "wake_up",
      "uri": "spotify:user:rudolfix-us:playlist:2jHR9oCmXl1wFc3o6EDqH3"
    }
  ]
}
```

Special HTTP status codes:

1. 428: user data is not processed and playlist cannot be generated. it typically take from 15 to 2 minutes. currently (demo) this is a random time

####/me/playlists/:playlist_type
Input parameters
**:playlist_type** tells which plalist to set up ( **wake_up** | **fall_asleep**). Mandatory parameter
Query string parameters
**desired_length** - desired playlist length in milliseconds. Please note that actual playlist length will be different 
as it is consturcted with the whole tracks. Mandatory parameter.
Returns
*Playlist* object

```javascript
curl -X POST "http://wakeupapp.dev.army/me/playlists/wake_up?desired_length=30000" -H "Authorization: ...."
{
  "result": {
    "length": 415379,
    "type": "wake_up",
    "uri": "spotify:user:rudolfix-us:playlist:2jHR9oCmXl1wFc3o6EDqH3"
  }
}
```

Special HTTP error codes:
1. 428: user data is not processed and playlist cannot be generated. it typically take from 15 to 2 minutes. currently (demo) this is a random time

Example Api Session
-----------------------

1. Execute spotify login. It will end by calling /swap on the server.
  Swap method will create empty user account, generate access token and encrypted refresh token that must be used for authorization.
  Swap method will start generation of the user’s music graph which is later used to construct playlists.
  Swap method will set desired length for user's playlists to *30 minutes*
2. Swap method will fail for free spotify users. You can always re-login later.
3. You can use GET /me/playlists/ to check if music graph is ready.
4. When graph is ready, playlists with default length will be created on first GET
5. At this point playlists are ready and will be always available.
6. When graph is ready, client may set playlist length for both playlist types with POST. Playlist content will be re-created even if length is not changed


Error Handling
------------------------------

###Api Service

Same HTTP status codes should be handled in the same way.

|status code|description|
-----------|------------|
400|Bad Request. Parameters to request are invalid. See body for details.
401|Unauthorized. Access to service denied. **You must re-login user with swap service to recover** See body for details
403|Fobidden. Client will not be serverd no matter what. See body for details
428|Precondition Needed. See /me/playlist method
500|Internal Server error. Try again later ;>

```javascript
{
  "error": {
    "code": "PlaylistIncorrectDesiredLength",
    "message": "Playlists length can be from 0 to 4800000, actual value is 30000000",
    "status": 400
  }
}
```
Please note that body format is compatible with Spotify API error responses
See /sleep_server/api/exceptions for possible codes (they are exception class names)


###Swap Service
Swap service transparently returns Spotify status codes and error messages.
*Check what will happen in case of free spotify user, 403 will be returned*


Spotify App Configuration
----------------------------
*Wakeup Playlist Generator* spotify app with client id 3547ee3842f24500aded0f5a0afe11a5 is used both for dev and prod
environments (todo: create separate app for prod env.)
This app must be configured properly to allow mobile clients to login
1. Register iOS/Android bundle (like sleep.luxury8.com) (https://developer.spotify.com/technologies/spotify-ios-sdk/)
2. Set up a auth callback with app url scheme (https://developer.spotify.com/technologies/spotify-ios-sdk/tutorial/)
3. Exactly the same callback must be set on the backend (/sleep_server/api/config.py:CLIENT_CALLBACK_URL. Spotify checks
if both match. 


Deployment Information
-----------------------
* API and Swap Service are deployed on http://wakeupapp.dev.army. (AWS/Frankfurt/Micro)
* There is admin/test service accessible on http://wakeupapp.dev.army/admin/dashboard. After login you'll see your
Authorization header you may use to test with curl


Notes On Mockup
------------------------
Mockup works like final service, except playlists are not smartly generated. Currently there are two template playlists
1. https://open.spotify.com/user/1130122659/playlist/1v1Do2ukgKZ64wCuOrBnug (wake up)
2. https://open.spotify.com/user/1130122659/playlist/4rk4vb5hjM2jC5HFaOKRAL (fall asleep)
(Sarnecka is the owner) Playlist content is copied and then truncated to desired length. Finally it is stored in current
user Spotify account and available for playback
*I've found out that some songs available in DE for Aga are not available in PL for me, possible huge fuckup with
playback length - some songs will be skipped*



Development Environment
-------------------------
Vagrant up in root folder & add 127.0.0.1 dev.wakeupapp.com on host machine, vagrant slave is fully provisioned