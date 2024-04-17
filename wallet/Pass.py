import decimal
import hashlib
from io import BytesIO, BufferedReader
import json
import subprocess
import zipfile
import tempfile
from uuid import uuid4

from wallet.PassInformation import PassInformation
from typing import Optional, List, Union
from wallet.PassProps import Barcode, Location, IBeacon, NFC
from .exceptions import PassParameterException


def pass_handler(obj):
    """Pass Handler"""
    if hasattr(obj, "json_dict"):
        return obj.json_dict()
    # For Decimal latitude and logitude etc.
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    return obj


class Pass:
    def __init__(
        self,
        pass_information: PassInformation,
        pass_type_identifier: str,
        team_identifier: str,
        organization_name: str,
        *,
        serial_number: str = str(uuid4()),
        description: str = "pass description",
        background_color: Optional[str] = None,
        foreground_color: Optional[str] = None,
        label_color: Optional[str] = None,
        logo_text: Optional[str] = None,
        barcodes: Optional[Barcode] = None,
        show_strip_img: bool = False,
        web_service_url: str = None,
        authentication_token: str = None,
        locations: List[Location] = None,
        ibeacons: List[IBeacon] = None,
        relevant_date: str = None,
        associated_store_identifiers: list = None,
        app_launch_url: str = None,
        user_info: json = None,
        expriration_date: str = None,
        voided: bool = False,
        nfc: NFC = None
    ) -> None:
        """
        Prepare Pass
        :params pass_information: Instance of the following classes :
                - StoreCard
                - BoardingPass
                - Coupon
                - EventTicket
                - Generic

        :params pass_type_identifier: Pass type identifier, as
            issued by Apple. The value must
            correspond with your signing certificate. Used for grouping.

        :params organization_name: Display name of the organization
            that originated and signed the pass.

        :params team_identifier: Team identifier of the organization
            that originated and
            signed the pass, as issued by Apple.

        :params serial_number: Serial number that
            uniquely identifies the pass.

        :params description: Brief description of
            the pass, used by the iOS
            accessibility technologies.

        :params background_color: background color of the pass

        :params foreground_color: Foreground color of the pass

        :params label_color: Color of the label text

        :params logo_text: Text displayed next to the logo

        :params barcode:  Information specific to barcodes.

        :params show_strip_img: If true, the strip image is displayed

        :params web_service_rul: If present, authenticationToken must
            be supplied

        :params authentication_token: The authentication token to use with
            the web service

        :params locations: Locations where the pass is relevant.

        :params relevent_date:  Date and time when the pass becomes relevant


        :params associated_store_identifiers: A list of iTunes Store item
            identifiers for
            the associated apps.

        :params user_info: Additional hidden data in json for the passbook

        :params expriration_date: date where pass becomes expired

        :params voided: make a pass expire

        """

        self._files = {}  # Holds the files to include in the .pkpass
        self._hashes = {}  # Holds the SHAs of the files array

        # Standard Keys that required by Apple
        self.teamIdentifier = team_identifier
        self.passTypeIdentifier = pass_type_identifier
        self.organizationName = organization_name
        self.serialNumber = serial_number
        self.description = description
        self.formatVersion = 1

        # Visual Appearance Keys, optional attributes
        self.backgroundColor = background_color
        self.foregroundColor = foreground_color
        self.labelColor = label_color
        self.logoText = logo_text
        if barcodes:
            self.barcodes = [*barcodes]
        else:
            self.barcodes = []
        self.suppressStripShine = show_strip_img

        # Web Service Keys
        self.webServiceURL = web_service_url
        self.authenticationToken = authentication_token

        # Relevance Keys
        self.locations = locations
        self.ibeacons = ibeacons
        self.relevantDate = relevant_date
        self.associatedStoreIdentifiers = associated_store_identifiers
        self.appLaunchURL = app_launch_url
        self.userInfo = user_info

        self.exprirationDate = expriration_date
        self.voided = voided
        if nfc:
            self.NFC = nfc

        self.passInformation = pass_information

    def add_file(
        self, name: str, file_handle: Union[BufferedReader, bytes]
    ) -> None:
        """
        Add new file to the pass files
        :params name: String name
        :params file_handle: File Handle
        """
        if type(file_handle) == bytes:
            self._files[name] = file_handle
        elif type(file_handle) == BufferedReader:
            self._files[name] = file_handle.read()

    def create(
        self,
        certificate: str,
        key: str,
        wwdr_certificate: str,
        password: Optional[str] = False,
        file_name: Optional[str] = None,
        filemode: bool = True,
    ):
        """
        Create .pkass file
        """
        pass_json = self._create_pass_json()
        manifest = self._create_manifest(pass_json)
        signature = self._create_signature(
            manifest, certificate, key, wwdr_certificate, password, filemode
        )
        if not file_name:
            file_name = BytesIO()
        pkpass_file = self._create_zip(
            pass_json, manifest, signature, file_name=file_name
        )
        return pkpass_file

    def _create_pass_json(self):
        """
        Create Json Pass Files
        """
        return json.dumps(self, default=pass_handler).encode("utf-8")

    def _create_manifest(self, pass_json: bytes):
        """
        Creates the hashes for the files and adds them
        into a json string
        """
        self._hashes["pass.json"] = hashlib.sha1(pass_json).hexdigest()
        for filename, filedata in self._files.items():
            self._hashes[filename] = hashlib.sha1(filedata).hexdigest()
        return json.dumps(self._hashes).encode("utf-8")

    def _create_signature(
        self,
        manifest: bytes,
        certificate: str,
        key: str,
        wwdr_certificate: str,
        password: str,
        filemode: bool,
    ) -> bytes:
        """Create and Save Signature"""
        if not filemode:
            # Use Tempfile
            cert_file = tempfile.NamedTemporaryFile(mode="w")
            cert_file.write(certificate)
            cert_file.flush()
            key_file = tempfile.NamedTemporaryFile(mode="w")
            key_file.write(key)
            key_file.flush()
            wwdr_file = tempfile.NamedTemporaryFile(mode="w")
            wwdr_file.write(wwdr_certificate)
            wwdr_file.flush()
            certificate = cert_file.name
            key = key_file.name
            wwdr_certificate = wwdr_file.name

        openssl_cmd = [
            "openssl",
            "smime",
            "-binary",
            "-sign",
            "-certfile",
            wwdr_certificate,
            "-signer",
            certificate,
            "-inkey",
            key,
            "-outform",
            "DER",
            "-passin",
            f"pass:{password}",
        ]

        process = subprocess.Popen(
            openssl_cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        process.stdin.write(manifest)
        out_data, error = process.communicate()
        if process.returncode != 0:
            raise Exception(error)

        return out_data

    def _create_zip(
        self,
        pass_json: bytes,
        manifest: bytes,
        signature: bytes,
        file_name: Union[BytesIO, str],
    ) -> Union[BytesIO, str]:
        """
        Creats .pkass ZIP Archive
        """
        z_file = zipfile.ZipFile(file_name or "pass.pkpass", "w")
        z_file.writestr("signature", signature)
        z_file.writestr("manifest.json", manifest)
        z_file.writestr("pass.json", pass_json)
        for filename, filedata in self._files.items():
            z_file.writestr(filename, filedata)
        z_file.close()
        return file_name

    def json_dict(self) -> dict:
        """
        Return Pass as JSON Dict
        """
        simple_fields = [
            "description",
            "formatVersion",
            "organizationName",
            "passTypeIdentifier",
            "serialNumber",
            "teamIdentifier",
            "suppressStripShine",
            "relevantDate",
            "backgroundColor",
            "foregroundColor",
            "labelColor",
            "logoText",
            "ibeacons",
            "userInfo",
            "voided",
            "associatedStoreIdentifiers",
            "appLaunchURL",
            "exprirationDate",
            "webServiceURL",
            "authenticationToken",
        ]
        data = {}
        data[self.passInformation.jsonname] = self.passInformation.json_dict()
        for field in simple_fields:
            if hasattr(self, field):
                content = getattr(self, field)
                if content:
                    data[field] = content

        if self.barcodes:
            data["barcodes"] = []
            for barcode in self.barcodes:
                data["barcodes"].append(barcode.json_dict())

        if self.locations:
            data["locations"] = []
            for location in self.locations:
                data["locations"].append(location.json_dict())
            if len(data["locations"]) > 10:
                raise PassParameterException("Field locations has<10 entries")

        if self.ibeacons:
            data["ibeacons"] = []
            for ibeacon in self.ibeacons:
                data["ibeacons"].append(ibeacon.json_dict())

        if self.NFC:
            data["nfc"] = self.NFC.json_dict()

        requied_fields = [
            "description",
            "formatVersion",
            "organizationName",
            "organizationName",
            "serialNumber",
            "teamIdentifier",
        ]
        for field in requied_fields:
            if field not in data:
                raise PassParameterException(f"Field {field} missing")
        return data
