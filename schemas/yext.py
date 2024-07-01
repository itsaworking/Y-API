import pydantic
from pydantic import constr, root_validator
from typing import Optional, List


class YextImage(pydantic.BaseModel):
    url: str
    type: str


class YextCategory(pydantic.BaseModel):
    id: str
    name: str


class YextEmail(pydantic.BaseModel):
    address: str


class YextVideo(pydantic.BaseModel):
    url: str


class YextPhoneNumber(pydantic.BaseModel):
    countryCode: Optional[str]
    number: constr(min_length=10, max_length=10, regex=r'[0-9]+')


class YextPhone(pydantic.BaseModel):
    number: YextPhoneNumber
    type: Optional[str]
    description: Optional[str]


class YextUrl(pydantic.BaseModel):
    url: str
    type: Optional[str]
    description: Optional[str]
    displayUrl: Optional[str]


class YextSpecialOffer(pydantic.BaseModel):
    url: Optional[str]
    message: Optional[str]


class YextAddress(pydantic.BaseModel):
    address: str
    address2: Optional[str]
    displayAddress: Optional[str]
    city: str
    visible: bool
    state: str
    postalCode: str
    countryCode: Optional[str]


class YextGeoData(pydantic.BaseModel):
    displayLatitude: str
    displayLongitude: str


class YextHoursText(pydantic.BaseModel):
    display: str


class YextData(pydantic.BaseModel):
    images: List[YextImage] = []
    categories: List[YextCategory] = []
    payment_options: Optional[List[str]]
    emails: List[YextEmail] = []
    videos: List[YextVideo] = []
    urls: List[YextUrl] = []
    phones: List[YextPhone] = []
    special_offer: Optional[YextSpecialOffer]

    @root_validator(pre=True)
    def fix_phones(cls, values):
        dict_phones = [phone for phone in values.get("phones", []) if isinstance(phone, dict)]

        for phone in dict_phones:
            number = phone.get("number")
            if isinstance(number, str):
                phone["number"] = {
                    "number": number,
                    "countryCode": phone.get("countryCode")
                }

        return values

    class Config:
        allow_mutation = False

    @property
    def logo_url(self):
        for img in self.images:
            if img.type == "LOGO":
                return img.url

    @property
    def gallery_images(self):
        return [img for img in self.images if img.type == "GALLERY"]

    @property
    def website_url(self):
        for url in self.urls:
            type = (url.type or url.description or "").lower()
            if type == "website":
                return url.url

    @property
    def main_phone(self):
        for phone in self.phones:
            if phone.type == "MAIN":
                return phone.number.number


class YextListingCreate(pydantic.BaseModel):
    yextId: str
    partnerId: Optional[str]
    name: str
    address: YextAddress
    phones: List[YextPhone] = []
    categories: List[YextCategory] = []
    description: str
    emails: List[YextEmail] = []
    geoData: YextGeoData
    images: List[YextImage] = []
    specialOffer: Optional[YextSpecialOffer]
    urls: List[YextUrl] = []
    videos: List[YextVideo] = []
    paymentOptions: List[str] = []
    twitterHandle: Optional[str]
    facebookPageUrl: Optional[str]
    hoursText: Optional[YextHoursText]

    @pydantic.validator('phones')
    def must_have_main_phone(cls, phones):
        for phone in phones:
            if phone.type == "MAIN":
                return phones
        raise ValueError("phone of type MAIN is required")


class YextListingUpdate(pydantic.BaseModel):
    yextId: str
    partnerId: Optional[str]
    name: Optional[constr(min_length=1)]
    address: Optional[YextAddress]
    phones: Optional[List[YextPhone]]
    categories: Optional[List[YextCategory]]
    description: Optional[str]
    emails: Optional[List[YextEmail]]
    geoData: Optional[YextGeoData]
    images: Optional[List[YextImage]]
    specialOffer: Optional[YextSpecialOffer]
    urls: Optional[List[YextUrl]]
    videos: Optional[List[YextVideo]]
    paymentOptions: Optional[List[str]]
    twitterHandle: Optional[str]
    facebookPageUrl: Optional[str]
    hoursText: Optional[YextHoursText]


class YextListingSuppress(pydantic.BaseModel):
    listingId: str
    suppress: bool
    canonicalListingId: Optional[str]
