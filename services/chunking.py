def chunking_section(section:dict)-> list[dict]:

    if section['section_type']=="atomic":
        return chunk_atomic_units(section)
    if section["section_type"]=="narrative":
        return chunking_narrative_section(section)
    return []

def chunk_atomic_units(section:dict)-> list[dict]:
    return [
        {
            "section_header": section['header'],
            "chunk_text": "\n".join(section['content']),
            "section_type": "atomic",
            "page_no": section['page_no']
        }
    ]

def chunking_narrative_section(section: dict)-> list[dict]:

    text_blocks=section['content']

#step1: put everything in one chunk

    full_text="\n".join(text_blocks)
    if single_question_test(full_text):
        return [
            {
                "section_header": section['header'],
                "chunk_text": full_text,
                "section_type": "narrative",
                "page_no": section['page_no']
            }
        ]

#Step 2: split the full chunk into simmilar chunks based on some logic(single question test)

    chunks=[]
    current=[]

    for block in text_blocks:
        current.append(block)
        check_text="\n".join(current)

        if single_question_test(check_text):
            chunks.append({
                "section_header": section['header'],
                "chunk_text": check_text,
                "section_type": "narrative",
                "page_no": section['page_no']
            }
                
            )
            current=[]
        
#step 3: If anything is left at the end from the above one in the current [] then join it in the chunks.
    if current:
        leftover_text="\n".join(current)
        chunks.append({
            "section_header": section['header'],
            "chunk_text": leftover_text,
            "section_type": "narrative",
            "page_no": section['page_no']
        })
    return chunks

def single_question_test(text:str)-> bool:

    text=text.strip()

    if len(text)<200:
        return False
    text_lower=text.lower()
    
    #Test 1: obvious dependency test
    forbidden_ref_words=[
        "as shown above",
        "as described above",
        "as mentioned above", 
        "as shown below",
        "as described below",
        "as mentioned below",
        "seen above",
        "seen below",
        "as per the table",
        "as per the figure",
        "refer to the table",
        "refer to the figure",
        "this table"
    ]

    if any(tex in text_lower for tex in forbidden_ref_words):
        return False
    
    #Test2: Dangling openers

    dangling_openers=[
        "however",
        "furthermore",
        "moreover",
        "in addition",
        "additionally",
        "consequently",
        "therefore",
        "thus",
        "nevertheless",
        "nonetheless",
        "on the other hand",
        "in contrast",
        "similarly",
        "likewise",
        "due to the following",
        "including the following",
        "as follows:",
        "the following:",
        "such as:"
    ]

    if any(text_lower.startswith(openers) for openers in dangling_openers):
        return False
    
    #Test 2: check for the boundary conditions like fullstop at the end.
    if "." not in text_lower:
        return False
    
    #Test 4 boundary integrity
    bad_starts=(
        
        "and", "but", "or", "therefore")
    
    if text_lower.startswith(bad_starts):
        return False


    return True


def returning_allchunks(sections:dict)-> list[dict]:
    all_chunks=[]

    for section in sections:
        section_chunks= chunking_section(section)
        all_chunks.extend(section_chunks)
    return all_chunks