from requests import get

print(
  """PINGBRIDGE

  Live notifications on your favourite bridge partnership!

  How it works?

  Paste a link to the live results (pbn)
  Select the couple to follow
  Enjoy!

  """)

url = "https://www.bridge.no/var/ruter/html/9901/2021-08-04.pbn"
pair_number = 76

response = get(url).content

print(response)








