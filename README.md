# py-pkpass

https://img.shields.io/badge/Test-83%25-green


Python library to read/write [Apple Wallet](http://developer.apple.com/library/ios/#documentation/UserExperience/Conceptual/PassKit_PG/Chapters/Introduction.html#//apple_ref/doc/uid/TP40012195-CH1-SW1) (.pkpass) files, see also [Pass Design and Creation](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/PassKit_PG/Creating.html)

This is a fork of https://github.com/Bastian-Kuhn/wallet , the original fork https://github.com/devartis/passbook

## Getting started 
```bash
git clone https://github.com/NafieAlhilaly/py-pkpass.git
```
move to py-pkpass dir
```bash
cd py-pkpass
```

create python virtual environment
```bash
python3 -m venv venv
```

activate your virtual environmetn
```bash
source <your-env-name>/bin/activate
```


## New Features
  * Direct Generation of passes without thee need to store them on a filesystem (if wanted)
  * Password less Keys possible if wanted
  * Validation of Fields and Passes including own Exception (PassParameterException)
  * Complete Refactored and Simplified Code (Still WIP)


## ToDos
  * Update of Getting Started
  * Add docker-compose
  * Validate data
  * Add NFC support
  * Full Example including which Fields are Possible


## Before creating a pkpass file you need to :
1. Create a Pass Type Id:
    1. Visit the [Visit the iOS Provisioning Portal](https://developer.apple.com/account/resources/certificates/list)
    2. On the left, click Identifiers
    3. From the type drop-down on the right, choose Pass Type IDs
    4. Next to Identifiers, click the + (plus) button.
    5. Select Pass Type IDs and click Continue
    6. Enter a description and an identifier (typically in the form `pass.com.yourcompany.some_name`) and click Continue
    7. Download the generated file
2. Double-click the pass file you downloaded to install it to your keychain
3. Export the pass certificate as a p12 file:
    1. Open Keychain Access
    2. Locate the pass certificate -- it should be under the login keychain, Certificates category.
    3. Right-click the pass and choose Export
    4. Make sure the File Format is set to Personal Information Exchange (.p12) and export to a convenient location.
4. Generate the necessary certificate and key .pem files
    1. Open Terminal and navigate to the folder where you exported the p12 file.
    2. Generate the pass pem file:

       ```sh
       openssl pkcs12 -in "Certificates.p12" -clcerts -nokeys -out certificate.pem
       ```
    3. Generate the key pem file:<br/>**Note** *you must set a password for the key pem file or you'll get errors when attempt to generate the pkpass file.*

       ```sh
       openssl pkcs12 -in "Certificates.p12" -nocerts -out key.pem
       ```
5. Generate the pem file for the Apple WWDR certificate (available from [developer.apple.com](http://developer.apple.com/certificationauthority/AppleWWDRCA.cer)) following the same steps as above.
6. Move all the pem files into your project


## Typical Usage

```python
from wallet.PassStyles import StoreCard
from wallet.Pass import Pass
from wallet.PassProps.Barcode import Barcode
import uuid
from wallet.Schemas.FieldProps import FieldProps


pass_type_identifier = "pass.com.yourcompany.some_name"
team_identifier = "ABCDE123"  # Your Apple team ID


card = StoreCard()
card.add_header_field(FieldProps(key="k2", value="69", label="Points"))
card.add_secondary_field(FieldProps(key="k3", value="Small shark", label="Level"))
card.add_back_field(FieldProps(key="k5", value="first backfield", label="bf1"))


passfile = Pass(
    **{
        "pass_information": card,
        "pass_type_identifier": pass_type_identifier,
        "organization_name": "organization_name",
        "team_identifier": team_identifier,
    }
)
passfile.logoText = "Sharks"


# charge_response.id is trackable via the Stripe dashboard
passfile.serialNumber = str(uuid.uuid4())
passfile.barcodes.append(Barcode(message="testing", ))
passfile.description = "some discription"
passfile.backgroundColor = "rgb(38, 93, 205)"
passfile.foregroundColor = "rgb(255, 255, 255)"
passfile.labelColor = "rgb(189, 189, 189)"


# Including the icon and logo is necessary for the passbook to be valid.
passfile.add_file("icon.png", open("shark-icon.png", "rb"))
passfile.add_file("icon@2x.png", open("shark-icon.png", "rb"))
passfile.add_file("icon@3x.png", open("shark-icon.png", "rb"))
passfile.add_file("logo.png", open("shark-icon.png", "rb"))
passfile.add_file("logo@2x.png", open("shark-icon.png", "rb"))
passfile.add_file("logo@3x.png", open("shark-icon.png", "rb"))
passfile.add_file("strip.png", open("sea.jpg", "rb"))
passfile.create(
    "signerCert.pem",
    "signerKey.pem",
    "wwdr.pem",
    password="password",
    file_name="test_pass.pkpass",
)
```
<img src="https://github.com/NafieAlhilaly/py-pkpass/blob/develop/Screenshot/pass_screenshot.png" alt="drawing" style="width:200px;"/>

### Notes

* You must use a password for your key.pem file. If you don't, the pass file won't be properly generated. You'll probably see errors like `PEM routines:PEM_read_bio:no start line` in your server's logs.
* `passfile.create()` writes the pass file to your server's filesystem. By default, it's written to the same directory as your script, but you can pass an absolute path (including the file name) to store elsewhere.
* `passfile.create()` returns the name of the generated file, which matches what you pass to it as the fifth parameter.
* Valid `cardInfo` constructors mirror the pass types defined by Apple. For example, `StoreCard()`, `BoardingPass()`, `Coupon()`, etc.
* The various "add field" methods (e.g. `addPrimaryField()`) take three unnamed parameters in the order `key`, `value`, `label`

An example Flask route handler to return the generated pass files:

```python
@application.route("/passes/<path:fname>")
def passes_proxy(fname):
    """static passes serve"""
    return send_from_directory("passes", fname, mimetype="application/vnd.apple.pkpass")
```

An example usage in a React app using Stripe and Stripe Elements to process payments and generate a store pass:

```javascript
paymentRequest.on('token', async (ev) => {
  try {
    const response = await fetch('https://your_server/charge', {
      method: 'POST',
      body: JSON.stringify({
        token: ev.token.id,
        amount: totalInCents,
        description: purchasedItems.join(',\n')
      }),
      headers: {'content-type': 'application/json'},
    });
    if (!response.ok) {
      throw new Error('There was a problem processing your payment.');
    }
    // Report to the browser that the payment was successful, prompting
    // it to download the pass file to the user's Wallet
    ev.complete('success');
    const pkpass = await response.json();
    window.location.href = `https://your_server/passes/${pkpass.filename}`;
  } catch (error) {
    throw new Error("There was a problem processing your payment.");
  }
});
```