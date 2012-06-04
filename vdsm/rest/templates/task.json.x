{
  "id": "$resource.uuid",
  "href": "/api/tasks/$resource.uuid",
  "verb": "$resource.props['taskInfo']['verb']",
  "message": "$resource.props['taskStatus']['message']",
  "code": $resource.props['taskStatus']['code'],
  "result": "$resource.props['taskStatus']['taskResult']",
  "state": "$resource.props['taskStatus']['taskState']",
  "actions": {
    "links": [ {
      "rel": "clear",
      "href": "/api/tasks/$resource.uuid/clear"
    }, {
      "rel": "revert",
      "href": "/api/tasks/$resource.uuid/revert"
    }, {
      "rel": "stop",
      "href": "/api/tasks/$resource.uuid/stop"
    } ]
  }
}
