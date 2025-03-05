# chatbot/views/utils/shared.py
def get_resource_name(resource):
    """Extracts the name from a FHIR resource."""
    if 'name' in resource and len(resource['name']) > 0:
        name_entry = resource['name'][0]
        if 'given' in name_entry and 'family' in name_entry:
            given = " ".join(name_entry.get('given', []))
            family = name_entry.get('family', '')
            return f"{given} {family}".strip()
        elif 'text' in name_entry and name_entry.get('text'):
            return name_entry.get('text').strip()
    return 'Unknown'