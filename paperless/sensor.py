"""Platform for sensor integration."""
from attr import attributes
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

import requests
import logging

import os.path

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([PaperlessSensor(hass, config_entry)], True)


class PaperlessSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, conf):
        """Initialize the sensor."""
        self._state = None
        self.hass = hass
        self.apikey = conf.data[CONF_API_TOKEN]
        self.host = conf.data[CONF_HOST]
        self.port = conf.data[CONF_PORT]
        self.conf_dir = str(hass.config.path()) + "/"
        self.dir = self.conf_dir + "www" + "/upcoming-media-card-images/paperless"
        self.docs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "paperless"

    @property
    def icon(self):
        return "mdi:note-multiple-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def matching_tag(self, id):
        result = list(filter(lambda x: x["id"] == id, self.tags))
        if len(result) == 1:
            return result[0]
        return {"name": "unkown", "color": "#ff0000"}

    @property
    def device_state_attributes(self):
        data = [
            {
                "title_default": "$title",
                "line1_default": "$date",
                "line2_default": "$number",
                "line3_default": "",
                "line4_default": "",
                "icon": "mdi:arrow-down-bold-circle",
            }
        ]

        for doc in self.docs:
            _LOGGER.warn(doc["created"])

            tag_list = []
            for tag_id in doc["tags"]:
                tag = self.matching_tag(tag_id)
                tag_list.append("{}{}".format(tag["color"], tag["name"]))
            tag_list = ", ".join(tag_list)

            data.append(
                {
                    "airdate": doc["created"],
                    "title": doc["title"],
                    "number": tag_list,
                    "poster": "/local/upcoming-media-card-images/paperless/{}.png".format(
                        doc["id"]
                    ),
                    "link": "http://{}:{}/api/documents/{}/preview/".format(
                        self.host, self.port, doc["id"]
                    ),
                }
            )

        attributes = {"count": self.document_count, "data": data}
        return attributes

    def write_image(self, pk):
        headers = {
            "Authorization": f"Token {self.apikey}",
            "Accept": "application/json; version=2",
        }
        resp = requests.get(
            "http://{}:{}/api/documents/{}/thumb/".format(self.host, self.port, pk),
            headers=headers,
        )
        if resp.status_code != 200:
            _LOGGER.error("fail {resp.status_code}")

        if not os.path.exists(self.dir):
            os.makedirs(self.dir, mode=0o777)

        # TODO: add clean up for images that aren't on list anymore

        filename = "{}/{}.png".format(self.dir, str(pk))
        if not os.path.isfile(filename):
            fo = open(filename, "wb")
            fo.write(resp.content)
            fo.close()
            _LOGGER.warn("write img {}".format(filename))

        return True

    def get_tags(self):
        headers = {
            "Authorization": f"Token {self.apikey}",
            "Accept": "application/json; version=2",
        }
        resp = requests.get(
            "http://{}:{}/api/tags/?format=json".format(self.host, self.port),
            headers=headers,
        )
        if resp.status_code != 200:
            _LOGGER.error("fail {resp.status_code}")
        return resp.json()["results"]

    def getDocumentCount(self, pk):
        headers = {
            "Authorization": f"Token {self.apikey}",
            "Accept": "application/json; version=2",
        }
        resp = requests.get(
            "http://{}:{}/api/documents/?format=json".format(self.host, self.port),
            headers=headers,
        )
        if resp.status_code != 200:
            _LOGGER.error("fail {resp.status_code}")

        json = resp.json()

        # TODO, make this less stupid (don't re-write), also expire old images
        self._state = "Online"
        self.write_image(pk)

        arr = json["results"]
        self.docs = arr

        for img in arr:
            self.write_image(img["id"])

        count = str(json["count"])
        return count

    async def async_update(self):
        self.tags = await self.hass.async_add_executor_job(self.get_tags)

        self.document_count = await self.hass.async_add_executor_job(
            self.getDocumentCount, 118
        )
